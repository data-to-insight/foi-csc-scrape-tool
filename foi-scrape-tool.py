import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta
import re

import certifi
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # intrim - mask Unverified HTTPS request warns

DEBUG = False # limit scrape depth and search breadth for testing


# add sources / 
BASE_URLS = {
    "WhatDoTheyKnow": "https://www.whatdotheyknow.com/search/",
    "HastingsCouncil": "https://www.hastings.gov.uk/my-council/freedom-of-information/date/"
}

## original
# def get_soup(url, max_attempts=2, delay=2):
#     """Fetch BeautifulSoup object from a given URL with retry mechanism."""
#     for attempt in range(1, max_attempts + 1):
#         try:
#             response = requests.get(
#                 url,
#                 headers={"User-Agent": "Mozilla/5.0"},
#                 timeout=10,
#             )
#             response.raise_for_status()
#             return BeautifulSoup(response.content, "html.parser")
#         except requests.RequestException as e:
#             print(f"Attempt {attempt} failed: {e}")
#             if attempt < max_attempts:
#                 time.sleep(delay)
#             else:
#                 print(f"Progress to next search: {attempt} of {max_attempts} page fails suggests we reached end of paginated search results.")
#                 return None


# NON-secure workaround for problem ssl cert at hastings
def get_soup(url, max_attempts=2, delay=2):
    """Fetch BeautifulSoup object from a given URL with retry mechanism (SSL verification disabled)."""
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

def scrape_foi_requests(search_terms, source="WhatDoTheyKnow", max_pages=None):
    """Handles scraping logic for a given FOI request source.
    only defaults to wdtk as this is our starting/default point for source data atm"""


    if source not in BASE_URLS:
        raise ValueError("Unsupported source. Choose from: " + ", ".join(BASE_URLS.keys()))
    # if source not in BASE_URLS and source != "HastingsCouncil":
    #     raise ValueError("Unsupported source. Choose from: " + ", ".join(BASE_URLS.keys()))
    
    base_url = BASE_URLS[source]
    all_data = []
    
    if source == "WhatDoTheyKnow":
        all_data = scrape_whatdotheyknow(search_terms, base_url, max_pages)
    elif source == "HastingsCouncil":
        all_data.extend(scrape_hastings_foi(search_terms))

    # elif source == "next data source":
    # # template for further sources. Need associated func() also! (and safe appending into all_data)
    #     pass # 
    


    df = pd.DataFrame(all_data)

    # any known row/record values to explicitly remove based on 'authority name' sub-string match
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
    non_relevant_titles = ["test request", "sample FOI", "irrelevant inquiry"]

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

        # Remove rows where authority name or request title contains unwanted words(defined above)
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
    """Scrapes FOI requests from WhatDoTheyKnow based on search term(s)."""
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
                    title_element = result.find("a")
                    request_title = title_element.text.strip()
                    request_url = "https://www.whatdotheyknow.com" + title_element["href"]
                    request_url_cleaned = title_element["href"].replace("/request/", "")
                    
                    requester_element = result.find("div", class_="requester")
                    authority_element = requester_element.find("a", href=True) if requester_element else None
                    authority_url = authority_element["href"] if authority_element else "Unknown"
                    authority_url_cleaned = authority_element["href"].replace("https://www.whatdotheyknow.com/body/", "") if authority_element else "Unknown"
                    authority_name = authority_element.text.strip() if authority_element else "Unknown"
                    
                    status_element = result.find("strong")
                    request_status = status_element.text.strip() if status_element else "Unknown"
                    
                    date_element = requester_element.find("time") if requester_element else None
                    request_date = date_element["datetime"] if date_element else "Unknown"
                    if request_date != "Unknown":
                        request_date = datetime.strptime(request_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                    
                    all_data.append({
                        "Source": "WhatDoTheyKnow",
                        "Search Term": search_term,
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
    
            # debug
            if DEBUG and page == 2: break


    return all_data



def scrape_hastings_foi(search_terms, base_url="https://www.hastings.gov.uk/my-council/freedom-of-information/date/", years=None):
    """Scrapes FOI requests from Hastings Council's FOI request listing pages."""

    if years is None:
        years = [2025, 2024, 2023]  # Define the years to scrape

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

            # Check if title contains any of our search terms
            if any(term.lower() in foi_title.lower() for term in search_terms) and foi_url:
                print(f"Processing relevant FOI request: {foi_title} ({foi_url})")

                foi_soup = get_soup(foi_url)
                if not foi_soup:
                    continue

                # Extract request ID
                request_id = foi_soup.find("h1").text.strip().replace("FOI request (", "").replace(")", "")

                # Extract request title
                request_title = foi_soup.find("h2").text.strip()

                # Extract request date (first date after 'Requested')
                request_date = None
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

                # Append structured data
                all_data.append({
                    "Source": "Hastings Council",
                    "Search Term": next((term for term in search_terms if term.lower() in foi_title.lower()), None),
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
    """Transforms FOI data by grouping requests under each authority as an HTML-friendly list."""

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
                    f'<a href="{row["Request URL"]}" target="_blank">View FOI</a></li>'
                    for _, row in x.iterrows()
                ]) + "</ul>"
            }),
            include_groups=False  # Explicitly exclude grouping columns (fixes deprecation warning)
        )
        .reset_index(drop=True)  # Remove redundant index
    )

    return grouped_df



def assign_ssd_foi_response_link(df):
    """
    Placeholder function to assign a url link to the associated SSD FOI Query resource, 
    within the SSD structure to enable analysts to download what they need to respond. 
    Currently, this just adds an empty col for future implementation.
    """
    # Add placeholder cols if don't exist
    if "FOIR" not in df.columns:
        df.insert(0, "FOIR", "")  # first col

    if "SSD-FOIR" not in df.columns:
        df.insert(len(df.columns), "SSD-FOIR", 
                '<a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests" target="_blank">SSD-Response</a>'
        )  # Insert as the last column with default link


    return df



import pandas as pd

def import_append_la_foi(external_data_file="submitted_foi.csv"):
    """
    Imports additional FOI data submitted by LA colleagues from CSV.

    Args:
        external_data_file (str): Path to CSV file containing extra FOIs.

    Returns:
        pd.DataFrame: The imported FOI DataFrame (if available), or an empty DataFrame if not.
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

    return pd.DataFrame()  # always returns df





# def save_to_html_alternative(df, filename="index.html"):
#     """Save Df to HTML file with enhanced formatting."""
#     page_title = "Freedom of Information Requests - Childrens Services Remit"
#     intro_text = (
#         '<p>This page provides a summary of Freedom of Information (FOI) requests made via the following sources:</p>'
#         '<ul>'
#         '<li><a href="https://www.whatdotheyknow.com">WhatDoTheyKnow.com</a></li>'
#         '<li>Local authority analyst-submitted records</li>'
#         '</ul>'
#         'By creating an automated/timely collated resource of FOI requests, we enable the potential to create the responses/development needed once and share it with any other local authorities who receive similar requests.<br/>'
#         'FOI requests are regularly submitted to multiple Local Authorities concurrently. By developing the required response query/data summary for one LA, we can then offer on-demand access to any analyst who might receive the same or similar request.' 
#         'Local authorities will need to have deployed the Standard Safeguarding Dataset (SSD) <a href="https://data-to-insight.github.io/ssd-data-model/">Standard Safeguarding Dataset (SSD)</a> and|or be a contributor to this FOI Network in order to download any of the pre-developed response queries from the <a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests">SSD tools repository</a>.<br/><br/>'
#         'Summary data shown below is scraped|aggregated from the above source(s) where FOI requests were considered to be within or relevant to the Children\'s Services Sector<br/>'
#         'The raw data incl. any additional data points not fitting the below web summary is available to <a href="https://github.com/data-to-insight/foi-scrape-tool/blob/main/foi_requests_summary.csv">download here</a>.'
#     )
    
#     disclaimer_text = (
#         'Disclaimer:<br/>'
#         'This summary is generated from publicly available data on the above listed sources<br/>'
#         'Due to variations in both source(s) and request formatting, some data shown may be incomplete or inaccurate. You should confirm details before using in critical reporting.<br/>'
#         'FOI requests into Scottish LAs, and some other related Organisations are included here for wider reference - with a view to potentially reducing this to LAs in England only at a later stage.<br/>'
#         'To view further details about each request and context use the active FOI request links within the summary table. <br/>'
#     )

#     submit_request_text = (
#         '<p>LA colleagues are encouraged to share both <a href="mailto:datatoinsight@gmail.com?subject=FOI%20Feedback">feedback+corrections</a> or details of any related FOI received by your Local Authority to assist and enable colleagues elsewhere.<br/>'
#         '<a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">Email us the FOI request summary detail</a> to contribute to this resource.</p>'
#     )
    
#     alternative_summary_format = ('<br/>We offer an <a href="https://github.com/data-to-insight/foi-scrape-tool/blob/main/index_alt_view.html">alternative view</a> of this summary page.'
#     )

#     adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")

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
#             th {{ background-color: #f2f2f2; text-align: left; }} /* Align headers left */
#             td {{ text-align: left; }} /* Align table data left */
#             a {{ color: blue; text-decoration: none; }}

#             /* Authority Name to fit content no warap */
#             td:nth-child(1), th:nth-child(1) {{ 
#                 white-space: nowrap;
#                 min-width: 100px;
#                 max-width: 300px;
#                 overflow: hidden;
#                 text-overflow: ellipsis;
#             }}
#         </style>
#     </head>


#     <body>
#         <h1>{page_title}</h1>
#         <p>{intro_text}</p>
#         <p>{disclaimer_text}</p>
#         <p>{submit_request_text}</p>
#         <p><b>Summary last updated: {adjusted_timestamp_str}</b></p>
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


# def save_to_html(df, filename="index_alt_view.html"):
#     """Save Df to HTML index pg"""
#     page_title = "Freedom of Information Requests - Childrens Services Remit"
#     intro_text = (
#         '<p>This page provides a summary of Freedom of Information (FOI) requests made via the following sources:</p>'
#         '<ul>'
#         '<li><a href="https://www.whatdotheyknow.com">WhatDoTheyKnow.com</a></li>'
#         '<li>Local authority analyst-submitted records</li>'
#         '</ul>'
#         'By creating an automated/timely collated resource of FOI requests, we enable the potential to create the responses/development needed once and share it with any other local authorities who receive similar requests.<br/>'
#         'FOI requests are regularly submitted to multiple Local Authorities concurrently. By developing the required response query/data summary for one LA, we can then offer on-demand access to any analyst who might receive the same or similar request.' 
#         'Local authorities will need to have deployed the Standard Safeguarding Dataset (SSD) <a href="https://data-to-insight.github.io/ssd-data-model/">Standard Safeguarding Dataset (SSD)</a> and|or be a contributor to this FOI Network in order to download any of the pre-developed response queries from the <a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests">SSD tools repository</a>.<br/><br/>'
#         'Summary data shown below is scraped|aggregated from the above source(s) where FOI requests were considered to be within or relevant to the Children\'s Services Sector<br/>'
#         'The raw data incl. any additional data points not fitting the below web summary is available to <a href="https://github.com/data-to-insight/foi-scrape-tool/blob/main/foi_requests_summary.csv">download here</a>.'
#     )
    
#     disclaimer_text = (
#         'Disclaimer:<br/>'
#         'This summary is generated from publicly available data on the above listed sources<br/>'
#         'Due to variations in both source(s) and request formatting, some data shown may be incomplete or inaccurate. You should confirm details before using in critical reporting.<br/>'
#         'FOI requests into Scottish LAs, and some other related Organisations are included here for wider reference - with a view to potentially reducing this to LAs in England only at a later stage.<br/>'
#         'To view further details about each request and context use the active FOI request links within the summary table. <br/>'
#     )

#     submit_request_text = (
#         '<p>LA colleagues are encouraged to share both <a href="mailto:datatoinsight@gmail.com?subject=FOI%20Feedback">feedback+corrections</a> or details of any related FOI received by your Local Authority to assist and enable colleagues elsewhere.<br/>'
#         '<a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">Email us the FOI request summary detail</a> to contribute to this resource.</p>'
#     )
    
#     alternative_summary_format = ('<br/>We offer an <a href="https://github.com/data-to-insight/foi-scrape-tool/blob/main/index.html">alternative view</a> of this summary page.'
#     )

#     adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")
    
#     # want an active link in output for each request (potentially actual request content is copyright)
#     df = df.copy()  
#     df.loc[:, "Request URL Link"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">FOI Content Detail</a>')
#     df.drop(columns=["Request URL"], inplace=True)


#     df_html = df.to_html(index=False, escape=False)
    
#     html_content = f"""
#     <html>
#     <head>
#         <title>{page_title}</title>
#         <style>
#             body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; }}
#             .table-container {{ overflow-x: auto; max-width: 100%; }}
#             table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
#             table, th, td {{ border: 1px solid #ddd; padding: 8px; }}
#             th {{ background-color: #f2f2f2; text-align: left; }} /* Align headers left */
#             td {{ text-align: left; }} /* Align table data left */
#             a {{ color: blue; text-decoration: none; }}

#             /* Authority Name and Request URL Link to fit content no warap */
#             td:nth-child(4), th:nth-child(4),  
#             td:nth-child(7), th:nth-child(7) {{ 
#                 white-space: nowrap; /* Prevent text wrapping */
#                 min-width: 100px; /* Ensure minimum width */
#                 max-width: 300px; /* Set a maximum width */
#                 overflow: hidden; /* Hide overflow */
#                 text-overflow: ellipsis; /* Add '...' if overflows */
#             }}
#         </style>
#     </head>
#     <body>
#         <h1>{page_title}</h1>
#         <p>{intro_text}</p>
#         <p>{disclaimer_text}</p>
#         <p>{submit_request_text}</p>
#         <p><b>Summary last updated: {adjusted_timestamp_str}</b></p>
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

from urllib.parse import urlparse

def extract_domain(url):
    """Extract main domain from URL, removing www. and any path/query params."""
    netloc = urlparse(url).netloc  # clean/grab domain and tld  e.g. 'www.whatdotheyknow.com'
    return netloc.replace("www.", "")  # Rem 'www.' if exists

def save_to_html(df, filename="index.html", alternative_view=False):
    """Save DataFrame to an HTML file with configurable formatting."""
    
    page_title = "Freedom of Information Requests - Children's Services Remit"

    # Generate sources list from BASE_URLS
    sources_list = "".join(
        f'<li><a href="{url}">{extract_domain(url)}</a></li>'
        for url in BASE_URLS.values()
    )
    # Append LA submitted record list item(this never in BASE_URLS)
    sources_list += '<li>Local authority (colleague-)submitted records</li>'

    intro_text = (
        '<p>This page provides a summary of Freedom of Information (FOI) requests published via the following sources:</p>'
        f'<ul>{sources_list}</ul>'
        'By creating an automated/timely collated resource of FOI requests, we enable the potential to create the responses/development needed once and share it with any other local authorities who receive similar requests.<br/>'
        'FOI requests are regularly submitted to multiple Local Authorities concurrently. By developing the required response query/data summary for one LA, we can then offer on-demand access to any analyst who might receive the same or similar request.'
        'Local authorities will need to have deployed the Standard Safeguarding Dataset (SSD) <a href="https://data-to-insight.github.io/ssd-data-model/">SSD</a> '
        'and|or be a contributor to this FOI Network in order to download pre-developed response queries from the '
        '<a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests">SSD tools repository</a>.<br/><br/>'
        'Summary data below is aggregated from the above source(s) where FOI requests were relevant to the Children\'s Services Sector.<br/>'
        'The raw data, including any additional fields, is available to <a href="foi_requests_summary.csv">download here</a>.'
    )
    
    disclaimer_text = (
        '<b>Disclaimer:</b><br/>'
        'This summary is generated from publicly available data from the listed sources. Verify before using in reporting.<br/>'
        'Due to variations in formatting, some data may be incomplete or inaccurate and some FOI Ref/IDs are not always available. <br/>'
        'FOI requests into Scottish LAs and other related organisations are included for wider reference—this may be narrowed to England-only LAs in future.<br/>'
        'For details on each request, use the active FOI Request URL links in the table below.<br/>'
    )

    submit_request_text = (
        '<p>LA colleagues are encouraged to share both <a href="mailto:datatoinsight@gmail.com?subject=FOI%20Feedback">feedback+corrections</a> or '
        '<a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">'
        'submit new FOI request details</a> to contribute to this resource.</p>'
    )
    
    alternative_summary_format = (
        f'<br/>We offer an <a href="index_alt_view.html">alternative summary view</a> of this page with additional/verbose detail.'
        if filename == "index.html" 
        else f'<br/>We offer an <a href="index.html">alternative summary view</a> of this page grouped by LA.'
    )



    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")

    # Apply different styling based on whether alternative view
    # the REquest URL col doesnt exist in the alt view, and la name also in different position
    if alternative_view:
        custom_styles = """
            /* Authority Name and Request URL to fit content no wrap */
            td:nth-child(4), th:nth-child(4),  
            td:nth-child(5), th:nth-child(5),
            td:nth-child(7), th:nth-child(7) {
                white-space: nowrap;
                display: block;
                min-width: 80px;
                max-width: 250px;
                overflow: hidden;
                text-overflow: ellipsis;
            }
        """
    else:
        custom_styles = """
            /* Authority Name column in grouped format */
            td:nth-child(1), th:nth-child(1) { 
                white-space: nowrap;
                min-width: 80px;
                max-width: 300px;
                overflow: hidden;
                text-overflow: ellipsis;
            }
        """

        # Apply format modifications for alternative view if required
        df = df.copy()  
        df.loc[:, "Request URL"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">View FOI</a>')


    df_html = df.to_html(index=False, escape=False)  # escape=False ensures HTML renders properly

    html_content = f"""
    <html>
    <head>
        <title>{page_title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; }}
            .table-container {{ overflow-x: auto; max-width: 100%; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
            table, th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; text-align: left; }}
            td {{ text-align: left; }}
            a {{ color: blue; text-decoration: none; }}

            {custom_styles}
        </style>
    </head>
    <body>
        <h1>{page_title}</h1>
        <p>{intro_text}</p>
        <p>{disclaimer_text}</p>
        <p>{submit_request_text}</p>
        <p><b>Summary last updated: {adjusted_timestamp_str}</p>
        <p>{alternative_summary_format}</p>
        <div class="table-container">
            {df_html}
        </div>
    </body>
    </html>
    """

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Summary saved to {filename}")


# These are the search terms used against whattheyknow site search
search_terms = ["looked after children", "children in need", "care leavers", "childrens social care", "child fostering", "childrens services", 
                "foster carer", "social workers", "adoption", "care order", "family support", "special educational needs"]

if DEBUG:
    search_terms = ["looked after children", "care leavers", "child fostering"]




# Generate FOI data records
df_whatdotheyknow = scrape_foi_requests(search_terms) # scraped FOIs from web
df_hastings = scrape_foi_requests(search_terms, source="HastingsCouncil") # scraped FOIs from Hastings Council
df_la_submitted = import_append_la_foi() # LA submitted FOIs from csv file

# Combine sources
df = pd.concat([df_whatdotheyknow, df_hastings, df_la_submitted], ignore_index=True)




# Not yet in operation as no FOI response solutions exist yet in SSD
df = assign_ssd_foi_response_link(df)  # Add placeholder SSD FOI Query|Code Link col


## Outputs
# CSV output
df_csv_output = df[["FOIR", "Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL", "Source", "Search Term", "SSD-FOIR"]]
df_csv_output.to_csv("foi_requests_summary.csv", index=False)


# reduce cols for ease of formatting on web
df_html_output = df[["FOIR", "Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL", "SSD-FOIR"]]

df_html_output_grouped = transform_foi_data_list_format(df_html_output)

# # HTML output 1
# df_html_output_grouped = transform_foi_data_list_format(df_html_output)
# save_to_html_alternative(df_html_output_grouped) # need to re-factor save_to_html to handle both scenarios/formats in one func

# # HTML output 2
# save_to_html(df_html_output)


# Save main/index summary page 
save_to_html(df_html_output_grouped, filename="index.html", alternative_view=True)

# Save verbose/prev view
save_to_html(df_html_output, filename="index_alt_view.html", alternative_view=False)

print("Scraping completed, saved to 'foi_requests_summary.csv' & 'index.html'")

