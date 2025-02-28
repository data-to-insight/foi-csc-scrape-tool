import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta

BASE_URL = "https://www.whatdotheyknow.com/search/"


def get_soup(url, max_attempts=3, delay=2):
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


def scrape_foi_requests(search_terms, max_pages=None):
    """Scrapes FOI requests from WhatDoTheyKnow based on multiple search terms."""
    all_data = []
    
    for search_term in search_terms:
        page = 1
        while True:
            if max_pages and page > max_pages:
                break
            
            search_url = f"{BASE_URL}{search_term.replace(' ', '%20')}?page={page}&query={search_term.replace(' ', '+')}"
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
                    request_url = title_element["href"].replace("/request/", "")
                    
                    requester_element = result.find("div", class_="requester")
                    authority_element = requester_element.find("a", href=True) if requester_element else None
                    authority_url = authority_element["href"].replace("https://www.whatdotheyknow.com/body/", "") if authority_element else "Unknown"
                    authority_name = authority_element.text.strip() if authority_element else "Unknown"
                    
                    status_element = result.find("strong")
                    request_status = status_element.text.strip() if status_element else "Unknown"
                    
                    date_element = requester_element.find("time") if requester_element else None
                    request_date = date_element["datetime"] if date_element else "Unknown"
                    if request_date != "Unknown":
                        request_date = datetime.strptime(request_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                    
                    all_data.append({
                        "Status": request_status,
                        "Date": request_date,
                        "Authority Name": authority_name,
                        "Request Title": request_title,                      
                        "Search Term": search_term
                        # "Request URL": request_url,
                        # "Authority ID": authority_url,

                    })
                except Exception as e:
                    print(f"Error parsing result: {e}")
            
            page += 1
            time.sleep(2)  # Avoid overloading the site
    
    return pd.DataFrame(all_data)


def save_to_html(df, filename="foi_summary.html"):
    """Save the DataFrame to an HTML file with enhanced formatting."""
    page_title = "Freedom of Information Requests Summary"
    intro_text = (
        'This page provides a summary of Freedom of Information (FOI) requests made through the WhatDoTheyKnow platform.<br/>'
        'It aggregates data from multiple search terms and presents key details about requests, including the authority they were submitted to, their status, and submission date.<br/><br/>'
        'The data is extracted directly from WhatDoTheyKnow and is subject to updates. Corrections or feedback are welcomed. <br/>'
        'The raw data is available to <a href="foi_requests.csv">download here</a>.'
    )
    
    disclaimer_text = (
        'Disclaimer:<br/>'
        'This summary is generated from publicly available data on '
        '<a href="https://www.whatdotheyknow.com">WhatDoTheyKnow</a>. <br/>'
        'Due to variations in request formatting, some data may be incomplete or inaccurate. '
        'For further details, please refer to the original request links. <br/>'
        'Feedback or corrections can be sent via the project repository.'
    )
    
    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")
    
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
            th {{ background-color: #f2f2f2; }}
            a {{ color: blue; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>{page_title}</h1>
        <p>{intro_text}</p>
        <p>{disclaimer_text}</p>
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


# Example Usage
search_terms = ["looked after children", "children in need", "care leavers", "childrens social care", "child fostering", "childrens services"]
df = scrape_foi_requests(search_terms)

# Save results to CSV
df.to_csv("foi_requests.csv", index=False)
print("Scraping completed and saved to 'foi_requests.csv'")

# Save results to an HTML summary page
save_to_html(df)


