import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta
import re

# add additional sources as requ
BASE_URLS = {
    "WhatDoTheyKnow": "https://www.whatdotheyknow.com/search/"
}


def get_soup(url, max_attempts=2, delay=2):
    """Fetch BeautifulSoup object from a given URL with retry mechanism."""
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
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
    
    base_url = BASE_URLS[source]
    all_data = []
    
    if source == "WhatDoTheyKnow":
        all_data = scrape_whatdotheyknow(search_terms, base_url, max_pages)

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
        df["LAs with same Request"] = df.groupby("normalised-request-title")["normalised-request-title"].transform("count") # las's with same request

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
    
            if page == 2:
                break
    return all_data


def transform_foi_data_list_format(df):
    """Transforms FOI data by grouping requests under each authority as an HTML-friendly list."""

    # Ensure the dataframe is sorted before grouping
    df = df.sort_values(by=["Authority Name", "Request Date"], ascending=[True, False])

    # Group by Authority Name and CSC FOIs on this LA
    grouped_df = df.groupby(["Authority Name", "CSC FOIs on this LA"]).apply(
        lambda x: "<ul>" + 
            "".join([
                f'<li><b>{row["Request Date"]}</b>: {row["Status"]} - {row["Request Title"]} '
                f'({row["LAs with same Request"]} requests) '
                f'<a href="{row["Request URL"]}" target="_blank">View FOI Detail</a></li>'
                for _, row in x.iterrows()
            ]) +
        "</ul>"
    ).reset_index(name="FOI Requests")

    return grouped_df



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

def save_to_html(df, filename="index.html", alternative_view=False):
    """Save DataFrame to an HTML file with configurable formatting."""
    
    page_title = "Freedom of Information Requests - Children's Services Remit"
    
    intro_text = (
        '<p>This page provides a summary of Freedom of Information (FOI) requests made via the following sources:</p>'
        '<ul>'
        '<li><a href="https://www.whatdotheyknow.com">WhatDoTheyKnow.com</a></li>'
        '<li>Local authority analyst-submitted records</li>'
        '</ul>'
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
        'This summary is generated from publicly available data from the listed sources.<br/>'
        'Due to variations in formatting, some data may be incomplete or inaccurate. Verify before using in reporting.<br/>'
        'FOI requests into Scottish LAs and other related organisations are included for wider reference—this may be narrowed to England-only LAs in future.<br/>'
        'For details on each request, use the active FOI request links in the table below.<br/>'
    )

    submit_request_text = (
        '<p>LA colleagues are encouraged to share both <a href="mailto:datatoinsight@gmail.com?subject=FOI%20Feedback">feedback+corrections</a> or '
        '<a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">'
        'submit new FOI request details</a> to contribute to this resource.</p>'
    )
    
    if alternative_view: 
        alternative_summary_format = (
            '<br/>We offer an <a href="index_alt_view.html">alternative summary view</a> of this page.'
            if not alternative_view else '<br/>We offer an <a href="index.html">alternative summary view</a> of this page.'
        )
    else:
        alternative_summary_format = (
            '<br/>We offer an <a href="index.html">alternative summary view</a> of this page.'
            if not alternative_view else '<br/>We offer an <a href="index.html">alternative summary view</a> of this page.'
        )

    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")

    # Apply format modifications for alternative view if required
    if not alternative_view:
        df = df.copy()  
        df.loc[:, "Request URL"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">View FOI Detail</a>')

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

            /* Authority Name and Request URL to fit content no wrap */
            td:nth-child(4), th:nth-child(4),  
            td:nth-child(7), th:nth-child(7) {{ 
                white-space: nowrap;
                min-width: 100px;
                max-width: 300px;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
        </style>
    </head>
    <body>
        <h1>{page_title}</h1>
        <p>{intro_text}</p>
        <p>{disclaimer_text}</p>
        <p>{submit_request_text}</p>
        <p><b>Summary last updated: {adjusted_timestamp_str}</b></p>
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

df = scrape_foi_requests(search_terms)


## Outputs
# CSV output
df_csv_output = df[["Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL", "Source", "Search Term"]]
df_csv_output.to_csv("foi_requests_summary.csv", index=False)


# reduce cols for ease of formatting on web
df_html_output = df[["Status", "Request Date", "CSC FOIs on this LA", "Authority Name", "Request Title", "LAs with same Request", "Request URL"]]

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

