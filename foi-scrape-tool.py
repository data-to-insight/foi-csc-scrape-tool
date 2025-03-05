import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta
import re
import os # mkdoc use
from tabulate import tabulate # summary output

from urllib.parse import urlparse

import certifi
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # intrim - mask Unverified HTTPS request warns

DEBUG = False # limit scrape depth and search breadth for testing


# add sources / 
BASE_URLS = {
    "WhatDoTheyKnow": "https://www.whatdotheyknow.com/search/",
    "HastingsCouncil": "https://www.hastings.gov.uk/my-council/freedom-of-information/date/"
    # to do:
    # https://opendata.camden.gov.uk/stories/s/Camden-Freedom-Of-Information-Response-Search/dwzc-va83/
}


# NON-secure workaround for problem ssl cert at hastings
def get_soup(url, max_attempts=2, delay=2):
    """
    Retrieve BeautifulSoup object from URL with retry handling.

    Args:
        url (str): Target webpage URL.
        max_attempts (int): Number of retry attempts. Defaults to 2.
        delay (int): Delay in seconds between retries. Defaults to 2.

    Returns:
        BeautifulSoup or None: Parsed HTML content or None if request fails.
    """

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                verify=False  # Disable SSL verification
                #  verify=certifi.where()  # SSL certificate verification

            )
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")

        except requests.exceptions.SSLError as ssl_err:
            print(f"SSL Error on attempt {attempt}: {ssl_err}. Trying again...")

        except requests.RequestException as e:
            print(f"Attempt {attempt} failed: {e}")

        if attempt < max_attempts:
            time.sleep(delay)
        else:
            print(f"Progress to next search: {attempt} of {max_attempts} page fails suggests we reached end of paginated search results.")
            return None


def scrape_foi_requests(search_terms, source="WhatDoTheyKnow", max_pages=None, start_year=None, end_year=2016):
    """
    Scrape FOI requests from given source and filter relevant results.

    Args:
        search_terms (list): Keywords to filter FOI requests.
        source (str): FOI data source. Defaults to "WhatDoTheyKnow".
        max_pages (int, optional): Maximum pages to scrape for paginated sources.
        start_year (int, optional): Earliest year to scrape. Defaults to current year.
        end_year (int): Oldest year to scrape. Defaults to 2016.

    Returns:
        pd.DataFrame: Scraped and filtered FOI request records.
    """

    if source not in BASE_URLS:
        raise ValueError("Unsupported source. Choose from: " + ", ".join(BASE_URLS.keys()))
    # if source not in BASE_URLS and source != "HastingsCouncil":
    #     raise ValueError("Unsupported source. Choose from: " + ", ".join(BASE_URLS.keys()))
    
    base_url = BASE_URLS[source]
    all_data = []
    
    if source == "WhatDoTheyKnow":
        all_data = scrape_whatdotheyknow(search_terms, base_url, max_pages)
    elif source == "HastingsCouncil":
        all_data.extend(scrape_hastings_foi(search_terms, base_url, start_year, end_year)) # hastings not paginated, hence not max_pages

    # elif source == "next data source":
    #   all_data.extend(scrape_nextdatasource_foi(search_terms, base_url, start_year, end_year))
   
    


    df = pd.DataFrame(all_data)

    # added filtering process more applicable for whatdotheyknow results, as these are very mixed in source/relevance
    # known row/record values to explicitly remove based on 'authority name' sub-string match
    # i.e. did we see anything in the output we just want to remove at face value. 
    non_relevant_la_names = ["Beauchamp", "Asheldham", 
                             "Belfast", "Omagh", "Ballymena", "Ballymoney", "Derry", 
                             "Northern Ireland", "Education Authority, Northern Ireland",
                             "Welsh Parliament",
                             "Village Council",
                             "School",  "Canal & River Trust", "Parish",  "Family Procedure Rule Committee", "General Register Office", "Partnership", "Natural Resources",
                             "Hughes Hall",  "Association", "Safeguarding", "Foundation", 
                             "Research Agency", "Statistics", "Ombudsman", "Office", "Service", "Commissioner",
                             "University", "College", "Academy",
                             "NSPCC", "NHS", "Health and Care", "Healthwatch", "Social Care Council"
                             "Ministry of Justice", "Constabulary", "Police", "National", "Ministry of Defence",
                             "Department for Education", "Department for Work and Pensions", "Department of Health", "Department of Health and Social Care", 
                             "Government", "Revenue and Customs", "House of Commons", "Supreme Court",
                             "Driver and Vehicle Licensing Agency"
                             ]
    non_relevant_titles = ["test request", "sample FOI", "irrelevant inquiry"] # defined, but not yet needed

    if not df.empty:
    
        # aggr an 'approx' count of how many sector related FOI each la/org has received
        # ensure consistent la/org name count
        df["normalised-authority-name"] = (
            df["Authority Name"]
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)  # multiple spaces to single space
            .str.encode("ascii", "ignore").str.decode("utf-8")  # Encode to ASCII for consistency
            .str.strip()  # leading/trailing spaces
        )
        df["normalised-request-title"] = (
            df["Request Title"]
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)  
            .str.encode("ascii", "ignore").str.decode("utf-8")
        )


        # Escape special chars in names to prevent regex issues
        pattern_la = "|".join(map(re.escape, non_relevant_la_names))
        pattern_titles = "|".join(map(re.escape, non_relevant_titles))

        # Remove rows where authority name or request title contains (known)unwanted words(defined above)
        df = df[~df["normalised-authority-name"].str.contains(pattern_la, case=False, na=False, regex=True)]
        df = df[~df["normalised-request-title"].str.contains(pattern_titles, case=False, na=False, regex=True)]


        # 'Date' to datetime for sorting
        df["Request Date"] = pd.to_datetime(df["Request Date"], format="%d/%m/%Y", errors="coerce")

        # most recent FOI request is kept
        df = df.sort_values(by="Request Date", ascending=False)
        df["Request Date"] = df["Request Date"].dt.strftime("%d/%m/%Y") # back to string in "DD/MM/YYYY" format

        # we're searching for term matches not scraping specific links, dups might occur
        # this must be done prior to any aggr count(s)
        # N.B further work needed to ensure we retain the best option here. #debug
        df = df.drop_duplicates(subset=["normalised-authority-name", "normalised-request-title"], keep="first")

        # aggr counts, how manyt requests per LA, how many LA's got same request
        df["CSC FOIs on this LA"] = df.groupby("normalised-authority-name")["normalised-authority-name"].transform("count")

        # count times Request Title appears (across all authorities)
        df["LAs with same Request"] = df.groupby("normalised-request-title")["normalised-request-title"].transform("count") # las's with same request (better if we could apply FOIRs!)

        # don't need helper col after this point
        df.drop(columns=["normalised-authority-name", "normalised-request-title"], inplace=True)

        # re-sort back to desired for output
        df = df.sort_values(by=["Authority Name"], ascending=True)
    
    return df


def scrape_whatdotheyknow(search_terms, base_url, max_pages):
    """
    Scrape FOI requests from WhatDoTheyKnow based on search terms.

    Args:
        search_terms (list): Keywords to filter relevant FOI requests.
        base_url (str): WhatDoTheyKnow search URL.
        max_pages (int): Maximum number of pages to scrape.

    Returns:
        list: Scraped FOI request records.
    """

    all_data = []
    
    for search_term in search_terms:
        page = 1
        while True:
            if max_pages and page > max_pages:
                break
            
            search_url = f"{base_url}{search_term.replace(' ', '%20')}?page={page}&query={search_term.replace(' ', '+')}"
            print(f"Scraping: {search_url}")
            
            soup = get_soup(search_url)
            if not soup:
                break
            
            results = soup.find_all("div", class_="request_listing")
            if not results:
                print("No more results found, stopping.")
                break
            
            for result in results:
                try:
                    # Extract title and request URL
                    title_element = result.find("a")
                    request_title = title_element.text.strip()
                    request_url = "https://www.whatdotheyknow.com" + title_element["href"]
                    request_url_cleaned = title_element["href"].replace("/request/", "")
                    
                    # Extract authority information
                    requester_element = result.find("div", class_="requester")
                    authority_element = requester_element.find("a", href=True) if requester_element else None
                    authority_url = authority_element["href"] if authority_element else "Unknown"
                    authority_url_cleaned = authority_element["href"].replace("https://www.whatdotheyknow.com/body/", "") if authority_element else "Unknown"
                    authority_name = authority_element.text.strip() if authority_element else "Unknown"
                    
                    # Extract request status
                    status_element = result.find("strong")
                    request_status = status_element.text.strip() if status_element else "Unknown"
                    
                    # Extract request date
                    date_element = requester_element.find("time") if requester_element else None
                    request_date = date_element["datetime"] if date_element else "Unknown"
                    if request_date != "Unknown":
                        request_date = datetime.strptime(request_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                                        
                    # Extract FOI reference number
                    desc_element = result.find("span", class_="desc")
                    foi_reference_number = ""
                    if desc_element:
                        match = re.search(r"\[FOI #(\d+)", desc_element.text)
                        if match:
                            foi_reference_number = match.group(1)

                    all_data.append({
                        "Source": "WhatDoTheyKnow",
                        "Search Term": search_term,
                        "FOIR": foi_reference_number,
                        "Request Title": request_title,
                        "Request URL": request_url,
                        "Request URL Cleaned": request_url_cleaned,
                        "Authority Name": authority_name,
                        "Authority URL": authority_url,
                        "Authority ID": authority_url_cleaned,
                        "Status": request_status,
                        "Request Date": request_date
                    })
                except Exception as e:
                    print(f"Error parsing result: {e}")
            
            page += 1
            time.sleep(2)  # Avoid overloading the site
    
    return all_data


def scrape_hastings_foi(search_terms, base_url, start_year=None, end_year=2016):
    """
    Scrape FOI requests from Hastings Council listing pages.

    Args:
        search_terms (list): Keywords to filter relevant FOI requests.
        base_url (str): Hastings Council FOI listing URL.
        start_year (int, optional): Start year for scraping (default: current year).
        end_year (int): End year for scraping (default: 2016 - this as far as they publish).

    Returns:
        list: Scraped FOI request records.
    """

    
    if start_year is None:
        start_year = datetime.today().year  # use current year

    years = list(range(start_year, end_year - 1, -1)) 

    all_data = []

    for year in years:
        year_url = f"{base_url}?year={year}"
        print(f"Scraping FOI requests for {year}: {year_url}")

        soup = get_soup(year_url)
        if not soup:
            continue  # Skip if failed to fetch

        # Find all FOI request links and titles
        foi_entries = soup.select("#FoiList ul li a")  # Select all FOI links within the list

        for entry in foi_entries:
            foi_title = entry.get("title", "").strip()
            foi_id = entry.get("href", "").strip()
            foi_url = f"{base_url}{foi_id}" if foi_id else None
            
            # Extract FOI request number from search results page
            foi_request_number = ""
            match = re.search(r"FOIR-(\d+)", foi_id)
            if match:
                foi_request_number = match.group(1)

            # Check if request title contains any of our search terms
            if any(term.lower() in foi_title.lower() for term in search_terms) and foi_url:
                print(f"Processing FOI request: {foi_title} ({foi_url})")

                foi_soup = get_soup(foi_url)
                if not foi_soup:
                    continue

                # Extract request ID from the sub-page, override search result if found
                request_id_element = foi_soup.find("h1")
                if request_id_element:
                    match = re.search(r"FOI[R]?-(\d+)", request_id_element.text)  # find both FOIR- and FOI-
                    if match:
                        foi_request_number = match.group(1)  # Override with more reliable sub-page ID

                # Extract request title
                request_title = foi_soup.find("h2").text.strip()

                # Extract request date (first date after 'Requested')
                request_date = ""
                main_div = foi_soup.find("div", class_="main")
                if main_div:
                    date_text = main_div.find(string=re.compile(r"Requested", re.IGNORECASE))
                    if date_text:
                        date_match = re.search(r"(\d{1,2} \w+ \d{4})", date_text)
                        if date_match:
                            request_date = datetime.strptime(date_match.group(1), "%d %B %Y").strftime("%d/%m/%Y")

                # Extract status from "Response" section
                status = "Successful"  # Default assumption
                response_heading = main_div.find(re.compile(r"^h\d$"), string=re.compile(r"Response", re.IGNORECASE))

                if response_heading:
                    response_text = response_heading.find_next_sibling().text.strip().lower()

                    if "information not held" in response_text:
                        status = "Information not held"
                    elif any(word in response_text for word in ["refused", "refusal"]):
                        status = "Refused"

                all_data.append({
                    "Source": "Hastings Council",
                    "Search Term": next((term for term in search_terms if term.lower() in foi_title.lower()), ""),
                    "FOIR": foi_request_number,  
                    "Request Title": request_title,
                    "Request URL": foi_url,
                    "Request URL Cleaned": foi_id.replace("?id=", ""),
                    "Authority Name": "Hastings Borough Council",
                    "Authority URL": "https://www.hastings.gov.uk",
                    "Authority ID": "hastings_borough_council",
                    "Status": status,
                    "Request Date": request_date,
                })

                # Avoid excessive requests
                time.sleep(2)

    return all_data




def transform_foi_data_list_format(df):
    """
    Transform FOI data into grouped HTML list format.

    Args:
        df (pd.DataFrame): FOI DataFrame.

    Returns:
        pd.DataFrame: Transformed DataFrame with grouped FOI requests per authority.
    """

    # Ensure the dataframe is sorted before grouping
    df = df.sort_values(by=["Authority Name", "Request Date"], ascending=[True, False])

    # Group by Authority Name and CSC FOIs on this LA
    grouped_df = (
        df.groupby(["Authority Name", "CSC FOIs on this LA"], as_index=False)
        .apply(
            lambda x: pd.Series({
                "FOI Requests": "<ul>" + "".join([
                    f'<li><b>{row["Request Date"]}</b>: {row["Status"]} - {row["Request Title"]} '  # Format FOIs as list items within the LA row
                    f'({row["LAs with same Request"]} requests) '
                    f'<a href="{row["Request URL"]}" target="_blank">View FOI</a></li>' # include direct link to foi request source page detail
                    for _, row in x.iterrows()
                ]) + "</ul>"
            }),
            include_groups=False  # Explicitly exclude grouping columns (fixes deprecation warning)
        )
        .reset_index(drop=True)  
    )

    return grouped_df



def assign_ssd_foi_response_link(df):
    """
    Add placeholder SSD FOI response link column.

    Args:
        df (pd.DataFrame): FOI df

    Returns:
        pd.DataFrame: Updated df with SSD FOI response link column.
    """

    if "FOIR" not in df.columns:
        df.insert(0, "FOIR", "")  # first col

    if "SSD-FOIR" not in df.columns:
        df.insert(len(df.columns), "SSD-FOIR", 
                '<a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests" target="_blank">SSD-Response</a>'
        )   # Insert as last column with default link until such time as we 
            #               a) have a bank of foi tools available and 
            #               b) figure out how to include the specific link for each foi here)


    return df



def import_append_la_foi(external_data_file="uploads/submitted_foi.csv"):
    """
    Import additional FOI data submitted by LA colleagues from CSV.

    Args:
        external_data_file (str): Path to CSV file containing extra FOIs.

    Returns:
        pd.DataFrame: The imported FOI DataFrame (if available), or empty DataFrame if not.
    """

    try:
        extra_df = pd.read_csv(external_data_file, dtype=str)  # Read all as strings to avoid type issues

        if extra_df.empty:
            print(f"Extra data file '{external_data_file}' contains headers but no data. Returning empty DataFrame.")
            return pd.DataFrame(columns=extra_df.columns)  # Return empty df

        print(f"Loaded additional FOI data from {external_data_file}.")
        return extra_df  # Return new df

    except FileNotFoundError:
        print(f"No extra data file found: {external_data_file}. Returning empty DataFrame.")
    except pd.errors.EmptyDataError:
        print(f"Extra data file '{external_data_file}' is empty (no headers or rows). Returning empty DataFrame.")

    return pd.DataFrame()  # always return df



def extract_domain(url):
    """
    Extract main domain from URL, removing 'www.' prefix.

    Args:
        url (str): Full URL.

    Returns:
        str: Cleaned domain name.
    """

    netloc = urlparse(url).netloc  # clean/grab domain and tld  e.g. 'www.whatdotheyknow.com'
    return netloc.replace("www.", "")  # Rem 'www.' if exists


# def save_to_html(df, filename="index.html", alternative_view=False):
#     """
#     Save FOI request DataFrame as an HTML summary page.

#     Args:
#         df (pd.DataFrame): FOI request data.
#         filename (str): Output HTML filename.
#         alternative_view (bool): Whether to apply alternative grouped view.

#     Returns:
#         None
#     """

    
#     page_title = "Freedom of Information Requests - Children's Services Remit"

#     # Generate sources list from BASE_URLS
#     sources_list = "".join(
#         f'<li><a href="{url}">{extract_domain(url)}</a></li>'
#         for url in BASE_URLS.values()
#     )
#     # Append LA submitted record list item(this never in BASE_URLS)
#     sources_list += '<li>Local authority (colleague-)submitted records</li>'

#     intro_text = (
#         '<p>This page provides a summary of Freedom of Information (FOI) requests published via the following sources:</p>'
#         f'<ul>{sources_list}</ul>'
#         'By creating an automated/timely collated resource of FOI requests, we enable the potential to create the responses/development needed once and share it with any other local authorities who receive similar requests.<br/>'
#         'FOI requests are regularly submitted to multiple Local Authorities concurrently. By developing the required response query/data summary for one LA, we can then offer on-demand access to any analyst who might receive the same or similar request.'
#         'Local authorities will need to have deployed the Standard Safeguarding Dataset (SSD) <a href="https://data-to-insight.github.io/ssd-data-model/">SSD</a> '
#         'and|or be a contributor to this FOI Network in order to download pre-developed response queries from the '
#         '<a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests">SSD tools repository</a>.<br/><br/>'
#         'Summary data below is aggregated from the above source(s) where FOI requests were relevant to the Children\'s Services Sector.<br/>'
#         'The raw data, including any additional fields, is available to <a href="downloads/foi_requests_summary.csv">download here</a>.'
#     )
    
#     disclaimer_text = (
#         '<b>Disclaimer:</b><br/>'
#         'This summary is generated from publicly available data from the listed sources. Verify before using in reporting.<br/>'
#         'Due to variations in formatting, some data may be incomplete or inaccurate and some FOI Ref/IDs are not always available. <br/>'
#         'FOI requests into Scottish LAs and other related organisations are included for wider reference—this may be narrowed to England-only LAs in future.<br/>'
#         'For details on each request, use the active FOI Request URL links in the table below.<br/>'
#     )

#     submit_request_text = (
#         '<p>LA colleagues are encouraged to share both <a href="mailto:datatoinsight@gmail.com?subject=FOI%20Feedback">feedback+corrections</a> or '
#         '<a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">'
#         'submit new FOI request details</a> to contribute to this resource.</p>'
#     )
    
#     alternative_summary_format = (
#         f'<br/>We offer an <a href="index_alt_view.html">alternative summary view</a> of this page with additional/verbose detail.'
#         if filename == "index.html" 
#         else f'<br/>We offer an <a href="index.html">alternative summary view</a> of this page grouped by LA.'
#     )



#     adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")

#     # Apply different styling based on whether alternative view
#     # the REquest URL col doesnt exist in the alt view, and la name also in different position
#     if alternative_view:
#         custom_styles = """
#             /* Authority Name and Request URL to fit content no wrap */
#             td:nth-child(4), th:nth-child(4),  
#             td:nth-child(5), th:nth-child(5),
#             td:nth-child(7), th:nth-child(7) {
#                 white-space: nowrap;
#                 display: block;
#                 min-width: 80px;
#                 max-width: 250px;
#                 overflow: hidden;
#                 text-overflow: ellipsis;
#             }
#         """
#     else:
#         custom_styles = """
#             /* Authority Name column in grouped format */
#             td:nth-child(1), th:nth-child(1) { 
#                 white-space: nowrap;
#                 min-width: 80px;
#                 max-width: 300px;
#                 overflow: hidden;
#                 text-overflow: ellipsis;
#             }
#         """

#         # Apply format modifications for alternative view if required
#         df = df.copy()  
#         df.loc[:, "Request URL"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">View FOI</a>')


#     df_html = df.to_html(index=False, escape=False)  # escape=False ensures HTML renders properly

#     html_content = f"""
#     <html>
#     <head>
#         <title>{page_title}</title>
#         <style>
#             body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; }}
#             .table-container {{ overflow-x: auto; max-width: 100%; }}
#             table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
#             table, th, td {{ border: 1px solid #ddd; padding: 8px; }}
#             th {{ background-color: #f2f2f2; text-align: left; }}
#             td {{ text-align: left; }}
#             a {{ color: blue; text-decoration: none; }}

#             {custom_styles}
#         </style>
#     </head>
#     <body>
#         <h1>{page_title}</h1>
#         <p>{intro_text}</p>
#         <p>{disclaimer_text}</p>
#         <p>{submit_request_text}</p>
#         <p><b>Summary last updated: {adjusted_timestamp_str}</p>
#         <p>{alternative_summary_format}</p>
#         <div class="table-container">
#             {df_html}
#         </div>
#     </body>
#     </html>
#     """

#     with open(filename, "w", encoding="utf-8") as f:
#         f.write(html_content)
    
#     print(f"Summary saved to {filename}")





def save_to_mkdocs(df, filename="docs/index.md"):
    """
    Save FOI request DataFrame as a Markdown summary page for MkDocs.

    Args:
        df (pd.DataFrame): FOI request data.
        filename (str): Output Markdown filename.

    Returns:
        None
    """

    disclaimer_text = """\
**Disclaimer:**

This summary is generated from publicly available data from the listed sources. Verify before using in reporting.
 Due to variations in formatting, some data may be incomplete or inaccurate.
 FOI requests into Scottish LAs and other related agencies are included for wider reference, potentially reduced to England-only LAs in the future.
 For details on each request, use the active 'View FOI' links in the table."""

    contribute_text = """\
**Collaborate:**

LA colleagues are encouraged to contribute. Use the following links to:

- [Provide feedback or corrections](mailto:datatoinsight@gmail.com?subject=FOI%20Feedback)  
- [Submit headline details(only) of any new FOI request made directly to your data team](mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E)
"""  


    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")
    last_updated_text = f"**Summary last updated:** {adjusted_timestamp_str}\n"

    if "Request URL" in df.columns:
        # this column not in the group variants of the output dfs
        df.loc[:, "Request URL"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">View FOI</a>')



    # opt 1 (tabulate) - can better control col widths
    
    num_cols = len(df.columns)
    max_widths = [None] * num_cols  # Generate max_widths list, setting all to None except "Request Title"

    if "Request URL" in df.columns:
        # then if we're handling the more detailed summary view, find & reduce size of title col to fit
        col_index = df.columns.get_loc("Request Title") # index of "Request Title" column
        max_widths[col_index] = 100  # Set limit for "Request Title"

    # if "FOI Requests" in df.columns:
    #     # handling the aggr summary, only one longer col here
    #     col_index = df.columns.get_loc("FOI Requests") # index of "Request Title" column
    #     max_widths[col_index] = 200  # Set limit for "Request Title"

    df_md = tabulate(df, headers="keys", tablefmt="github", numalign="left", stralign="left", maxcolwidths=max_widths, showindex=False)



    # # opt 2 (markdown)
    # # Convert DataFrame to Markdown table format
    # df_md = df.to_markdown(index=False)


    # Combine all text content
    md_content = f"{disclaimer_text}\n\n{contribute_text}\n\n{last_updated_text}\n{df_md}"

    # Ensure docs directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Save to Markdown file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Summary saved to {filename} for MkDocs processing.")


def shorten_headings_for_web(df):
    """
    Shorten specific column headings for improved web display.

    Args:
        df (pd.DataFrame): FOI request data.

    Returns:
        pd.DataFrame: DataFrame with updated col headings.
    """

    column_map = {
        "CSC FOIs on this LA": "LA CSC FOIs",
        "LAs with same Request": "FOI distributed"
    }

    # Rename cols if exist in df
    df = df.rename(columns={col: column_map[col] for col in df.columns if col in column_map})

    ## TEMP - (re)move / refactor later
    # cols to drop to ensure table fits output space
    columns_to_drop = ["SSD-FOIR", "FOIR"]  
    df.drop(columns=[col for col in columns_to_drop if col in df.columns], inplace=True)


    return df


def shorten_status_labels(df):
    """
    Shorten vals in 'Status' col to fit available browser/table space within summary table

    Args:
        df (pd.DataFrame): FOI request data.

    Returns:
        pd.DataFrame: DataFrame with updated 'Status' values.
    """

    status_map = {
        "Awaiting classification": "Awaiting",
        "Information not held": "Not Held",
        "Long overdue": "Overdue",
        "Partially successful": "Partial",
        "Successful": "Success",
        "Withdrawn by the requester": "Withdrawn"
    }

    # Apply mapping only if 'Status' column exists
    if "Status" in df.columns:
        df["Status"] = df["Status"].str.lower().str.strip() 
        for pattern, replacement in status_map.items():
            df["Status"] = df["Status"].apply(lambda x: re.sub(pattern, replacement, x, flags=re.IGNORECASE))

    return df

    return df


# search terms used against scraped site searches, incl whattheyknow 
search_terms = ["looked after children", "children in need", "care leavers", "childrens social care", "child fostering", "childrens services", 
                "foster carer", "social workers", "adoption", "care order", "family support", "special educational needs"]



if DEBUG:
    search_terms = ["care leavers"] # limit search terms
    max_pages = 2  # Limit scraping pages per search term
else:
    max_pages = None  # No limit in production

# Generate FOI data records
df_whatdotheyknow = scrape_foi_requests(search_terms, source="WhatDoTheyKnow", max_pages=max_pages) # scraped FOIs from web
df_hastings = scrape_foi_requests(search_terms, source="HastingsCouncil") # scraped FOIs from Hastings Council

df_la_submitted = import_append_la_foi() # LA submitted FOIs from csv file

# Combine sources
df = pd.concat([df_whatdotheyknow, df_hastings, df_la_submitted], ignore_index=True)



# Not yet in use as no/few FOI response solutions exist yet in SSD
df = assign_ssd_foi_response_link(df)  # Add placeholder SSD FOI Query|Code Link col


df = df.sort_values(by=["Authority Name", "Request Date"], ascending=[True, False])

## Outputs

# CSV output
df_csv_output = df[["FOIR", "Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL", "Source", "Search Term", "SSD-FOIR"]]
df_csv_output.to_csv("downloads/foi_requests_summary.csv", index=False)


# reduce cols for ease of formatting on web
df_html_output = df[["FOIR", "Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL", "SSD-FOIR"]]

# expanded output view from default df_html_output
df_html_output_grouped = transform_foi_data_list_format(df_html_output) # summarised view by LA/Agency



# # into htmlk versions (previous)
# save_to_html(df_html_output_grouped, filename="index.html", alternative_view=True) # Save main/index summarised view 
# save_to_html(df_html_output, filename="index_alt_view.html", alternative_view=False) # Save verbose/prev view

# into mkdocs (current)
df_html_output_grouped = shorten_headings_for_web(df_html_output_grouped)
df_html_output_grouped = shorten_status_labels(df_html_output_grouped)
save_to_mkdocs(df_html_output_grouped, filename="docs/foi_requests_summary_v1.md") # Save main/index summarised view 
df_html_output = shorten_headings_for_web(df_html_output)
df_html_output = shorten_status_labels(df_html_output)
save_to_mkdocs(df_html_output, filename="docs/foi_requests_summary_v2.md") # Save verbose/prev view


print("Scraping and doc creation completed")

