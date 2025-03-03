import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta

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
    # # template for further sources. Need associated func() also! 
    #     pass # 
    

    df = pd.DataFrame(all_data)

    # any known row/record values to explicitly remove based on 'authority name' sub-string match
    # i.e. did we see anything in the output we just want to remove at face value. 
    non_relevant_la_names = ["Beauchamp", "Asheldham", 
                             "Belfast", "Omagh", "Ballymena", "Ballymoney", "Derry", 
                             "Northern Ireland", "Education Authority, Northern Ireland",
                             "School",  "Canal & River Trust", "Parish Council",  "Family Procedure Rule Committee", "General Register Office", "Partnership", "Natural Resources",
                             "Hughes Hall",  "Association", "Safeguarding", "Foundation", 
                             "Research Agency", "Statistics", "Ombudsman", "Office", "Service", "Commissioner",
                             "University", "College", "Academy",
                             "NSPCC", "NHS", 
                             "Ministry of Justice", "Constabulary", "Police", "National",
                             "Department for Education", "Department for Work and Pensions", "Department of Health", "Department of Health and Social Care", 
                             "Government", "Revenue and Customs", "House of Commons", 
                             "Driver and Vehicle Licensing Agency"
                             ]
    non_relevant_titles = ["test request", "sample FOI", "irrelevant inquiry"]

    if not df.empty:
    
        # aggr an 'approx' count of how many sector related FOI each la/org has received
        # ensure consistent la/org name count
        df["normalised-authority-name"] = (
            df["Authority Name"]
            .str.lower()
            .str.replace(r"\s+", "", regex=True)
            .str.encode("ascii", "ignore").str.decode("utf-8")
        )

        df["normalised-request-title"] = (
            df["Request Title"]
            .str.lower()
            .str.replace(r"\s+", "", regex=True)
            .str.encode("ascii", "ignore").str.decode("utf-8")
        )

        # filter out any known non-relevant records explicitly
        df = df[~df["normalised-authority-name"].str.contains("|".join(non_relevant_la_names), case=False, na=False)]
        df = df[~df["normalised-request-title"].str.contains("|".join(non_relevant_titles), case=False, na=False)]


        # 'Date' to datetime for sorting
        df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")

        # most recent FOI request is kept
        df = df.sort_values(by="Date", ascending=False)

        # we're searching for term matches not scraping specific links, dups might occur
        # this must be done prior to any aggr count(s)
        # N.B further work needed to ensure we retain the best option here. #debug
        df = df.drop_duplicates(subset=["normalised-authority-name", "normalised-request-title"], keep="first")


        # aggr counts, how manyt requests per LA, how many LA's got same request
        df["CSC FOI Count"] = df.groupby("normalised-authority-name")["normalised-authority-name"].transform("count")

        # count times Request Title appears (across all authorities)
        df["LAs with same Request Title"] = df.groupby("normalised-request-title")["normalised-request-title"].transform("count") # las's with same request

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
                        "Date": request_date
                    })
                except Exception as e:
                    print(f"Error parsing result: {e}")
            
            page += 1
            time.sleep(2)  # Avoid overloading the site
    
    return all_data


def save_to_html(df, filename="index.html"):
    """Save the DataFrame to HTML file"""
    page_title = "Freedom of Information Requests - Childrens Services Remit"
    intro_text = (
        '<p>This page provides a summary of Freedom of Information (FOI) requests made via the following sources:</p>'
        '<ul>'
        '<li><a href="https://www.whatdotheyknow.com">WhatDoTheyKnow.com</a></li>'
        '<li>Local authorities self-submitted records</li>'
        '</ul>'
        'By creating an automated/timely collated resource of FOI requests, we enable the potential to create the responses/development needed once and share it with any other local authorities who receive similar requests.<br/>'
        'FOI requests are regularly submitted to multiple Local Authorities concurrently. By developing the required response query/data summary for one LA, we can then offer on-demand access to any analyst who might receive the same or similar request.' 
        'Local authorities will need to have deployed the Standard Safeguarding Dataset (SSD) <a href="https://data-to-insight.github.io/ssd-data-model/">Standard Safeguarding Dataset (SSD)</a> and|or be a contributor to this FOI Network in order to download any of the pre-developed response queries from the <a href="https://github.com/data-to-insight/ssd-data-model/tree/main/tools-ssd_foi_requests">SSD tools repository</a>.<br/><br/>'
        'Summary data shown below is scraped|aggregated from the above source(s) where FOI requests were considered to be within or relevant to the Children\'s Services Sector<br/>'
        'The raw data incl. any additional data points not fitting the below web summary is available to <a href="foi_requests.csv">download here</a>.'
    )
    
    disclaimer_text = (
        'Disclaimer:<br/>'
        'This summary is generated from publicly available data on the above listed sources<br/>'
        'Due to variations in both source(s) and request formatting, some data shown may be incomplete or inaccurate. You should confirm details before using in critical reporting'
        'FOI requests into Scottish LAs, and some other related Organisations are included here for wider reference - with a view to potentially reducing this to LAs in England only at a later stage.'

        'For further details about each request and context, please refer to the FOI request links. <br/>'
        'Feedback or corrections are welcomed and can be sent via the project repository.'
    )

    submit_request_text = (
        '<p>Share details of an FOI received by your Local Authority to enable others:<br/>'
        'Email us with the request detail to add to this page: <a href="mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E">Email D2I</a>.</p>'
    )
    
    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")
    
    # want an active link in output for each request (potentially actual request content is copyright)
    df = df.copy()  
    df.loc[:, "Request URL Link"] = df["Request URL"].apply(lambda x: f'<a href="{x}" target="_blank">FOI Content Detail</a>')
    df.drop(columns=["Request URL"], inplace=True)


    df_html = df.to_html(index=False, escape=False)
    
    html_content = f"""
    <html>
    <head>
        <title>{page_title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; }}
            .table-container {{ overflow-x: auto; max-width: 100%; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
            table, th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; text-align: left; }} /* Align headers left */
            td {{ text-align: left; }} /* Align table data left */
            a {{ color: blue; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>{page_title}</h1>
        <p>{intro_text}</p>
        <p>{disclaimer_text}</p>
        <p>{submit_request_text}</p>
        <p><b>Summary last updated: {adjusted_timestamp_str}</b></p>
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
df_csv_output = df[["Status", "Date", "CSC FOI Count", "Authority Name", "Request Title", "LAs with same Request Title", "Request URL", "Source", "Search Term"]]
df_csv_output.to_csv("foi_requests_summary.csv", index=False)

# HTML output
df_html_output = df[["Status", "Date", "CSC FOI Count", "Authority Name", "Request Title", "LAs with same Request Title", "Request URL"]]
save_to_html(df_html_output)

print("Scraping completed, saved to 'foi_requests_summary.csv' & 'index.html'")

