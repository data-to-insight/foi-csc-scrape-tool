# from git

import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta # start yr for scrape process
import pandas as pd
import PyPDF2
import io  # handling PDF byte stream

# limiters just to avoid full scrape hits during testing/debug
DEBUG_MODE = False  # False for full scrape
DEBUG_YEAR_LIMIT = 2025  # scrape single yr




pd.set_option('future.no_silent_downcasting', True) # explicitly opt-in to future pd behaviour (fillna()|ffill(),..)

# url paginated search (per year)
# Other ways to achieve this exist, but this simplest|reliable in terms of access most recent for each LA
base_url = "https://www.justiceinspectorates.gov.uk/hmiprobation/inspections?probation-inspection-type=inspection-of-youth-offending-services-2018-onwards"

def get_soup(url, max_attempts=2, delay=2):
    """Fetch Soup object from URL (incl.retries)"""
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            print(f"Attempt {attempt} failed: {e} - End of paginated results OR possible link failure.") # valid end of next page(s) OR failed
            if attempt < max_attempts:
                time.sleep(delay)
            else:
                return None

            
def clean_la_name(raw_name):
    """Clean and standardise the local authority name."""
    # Remove standard prefixes ('youth justice' & 'offending', 'services' is optional)
    cleaned_name = re.sub(
        r"(?i)^An\s+inspection\s+of\s+youth\s+(justice|offending)\s+(services\s+)?in\s+", 
        "", 
        raw_name
    ).strip()

    # Handle "Joint Inspections" (move suffix placement after cleanup)
    is_joint_inspection = re.match(r"(?i)^A\s+joint\s+inspection\s+of\s+", raw_name)
    cleaned_name = re.sub(r"(?i)^A\s+joint\s+inspection\s+of\s+", "", cleaned_name).strip()

    # SECOND CLEANUP: Remove lingering "youth justice services in" or "youth offending services in"
    cleaned_name = re.sub(
        r"(?i)^youth\s+(justice|offending)\s+services\s+in\s+", 
        "", 
        cleaned_name
    ).strip()

    # Add "- Joint_Inspection" suffix **only if it was a joint inspection**
    if is_joint_inspection:
        cleaned_name += " - JI" # Joint inspection

    # fixes for specific known issues
    fix_mappings = {
        "cumberlan d": "Cumberland",
        "southend -on-sea": "Southend-on-Sea",
        "leicestershire and": "Leicestershire",
        "stoke -on-trent": "Stoke-on-Trent",
        "services: Hull YJS": "Hull"
    }

    cleaned_name_lower = cleaned_name.lower()
    cleaned_name = fix_mappings.get(cleaned_name_lower, cleaned_name)

    return cleaned_name


def scrape_inspection_links(start_year=None, end_year=2018):
    """Scrape all inspection links for each year, ensuring no duplicates."""
    inspection_links = {}
    
    if start_year is None:
        start_year = datetime.now().year  # Default to current year

    if DEBUG_MODE:
        print(f"Debug Mode: Limiting scrape to year {DEBUG_YEAR_LIMIT}")
        start_year = DEBUG_YEAR_LIMIT
        end_year = DEBUG_YEAR_LIMIT

    for year in range(start_year, end_year - 1, -1):
        page = 0
        while True:
            paginated_url = f"{base_url}&paged={page}&year={year}"
            print(f"Fetching: {paginated_url}")
            
            soup = get_soup(paginated_url)
            if not soup:
                break  # Stop if the page is unavailable
            
            results = soup.find_all("div", class_="result inspection")
            if not results:
                print(f"No results found for year {year}, stopping pagination.")
                break
            
            for result in results:
                link_element = result.find("h4").find("a", href=True)
                if link_element:
                    report_url = link_element["href"]
                    report_name = link_element.text.strip()
                    
                    # Extract unique ref from URL (e.g., /readingyjs2024/ -> "readingyjs")
                    la_ref = re.sub(r"\d{4}$", "", report_url.split("/")[-2]).lower().strip()
                    
                    # Clean LA Name
                    la_name = clean_la_name(report_name)

                    # Extract Date of Publication by visiting full report page
                    publication_date = "Unknown"
                    report_soup = get_soup(report_url)
                    if report_soup:
                        meta_div = report_soup.find("div", id="inspection-meta")
                        if meta_div:
                            date_dt = meta_div.find("dt", string=lambda text: "Date of publication" in text)
                            if date_dt:
                                date_dd = date_dt.find_next_sibling("dd")
                                if date_dd:
                                    raw_date = date_dd.text.strip()
                                    try:
                                        # Convert to DD/MM/YYYY format
                                        # formatted_date = datetime.strptime(raw_date, "%d %B %Y").strftime("%d/%m/%Y")
                                        # Convert to DD/MM/YY format(testing for compact html view)
                                        formatted_date = datetime.strptime(raw_date, "%d %B %Y").strftime("%d/%m/%y") 

                                        publication_date = formatted_date
                                    except ValueError:
                                        print(f"⚠️ Failed to parse date for {la_name}: {raw_date}")

                    # Store results
                    if la_ref not in inspection_links:
                        inspection_links[la_ref] = {
                            "url": report_url,
                            "name": la_name,
                            "year": year,
                            "publication_date": publication_date  
                        }
                        print(f"Added: {la_name} ({year}) - Published on {publication_date}")
                    else:
                        print(f"🔁 Skipped duplicate: {la_name} ({year})")

            page += 1
            time.sleep(2)

    return inspection_links



# def scrape_inspection_links(start_year=None, end_year=2018):
#     """Scrape all inspection links for each year, ensuring no duplicates."""
#     inspection_links = {}
    
#     if start_year is None:
#         start_year = datetime.now().year  # set to current year
  
#     for year in range(start_year, end_year - 1, -1):
#         page = 0
#         while True:
#             paginated_url = f"{base_url}&paged={page}&year={year}"
#             print(f"Fetching: {paginated_url}")
            
#             soup = get_soup(paginated_url)
#             if not soup:
#                 break  # if page not fetched (==no more results showing)
            
#             results = soup.find_all("div", class_="result inspection")
#             if not results:
#                 print(f"No results found for year {year}, stopping pagination.")
#                 break
            
#             for result in results:
#                 link_element = result.find("h4").find("a", href=True)
#                 if link_element:
#                     report_url = link_element["href"]
#                     report_name = link_element.text.strip()
                    
#                     # get (unique?) ref from URL (e.g., /readingyjs2024/ -> "readingyjs")
#                     la_ref = re.sub(r"\d{4}$", "", report_url.split("/")[-2]).lower().strip()
                    
#                     # clean_la_name
#                     la_name = clean_la_name(report_name)  

#                     if la_ref not in inspection_links:
#                         inspection_links[la_ref] = {"url": report_url, "name": la_name, "year": year}  # cleaned `la_name`
#                         print(f"Added: {la_name} ({year})") # debug
#                     else:
#                         print(f"Skipped duplicate: {la_name} ({year})")
            
#             page += 1
#             time.sleep(2)
    
#     return inspection_links


# scraper and collect report links
inspection_data = scrape_inspection_links()

# debug / ref
print("\nFinal Inspection Links Collected:")
for ref, details in inspection_data.items():
    print(f"{details['year']}: {details['name']} -> {details['url']}")

    
def extract_ratings_from_pdf(pdf_url):
    """Extract ratings text from a PDF."""
    try:
        response = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
        pdf_file = io.BytesIO(response.content)
        reader = PyPDF2.PdfReader(pdf_file)
    except (requests.RequestException, PyPDF2.errors.PdfReadError) as e:
        print(f"⚠️ Failed to read PDF {pdf_url}: {e}")
        return "Ratings page not found"

    ratings_text = ""
    for page in reader.pages[2:]:  # skip first two pages (usually cover+contents page and they cause extract issues if left)
        text = page.extract_text()
        if text and ("ratings" in text.lower() or "overall rating" in text.lower()):
            ratings_text += text
            break  

    return ratings_text if ratings_text else "Ratings page not found"


# def parse_ratings(report_url, ratings_text, la_ref, la_name, publication_date):
#     """Parse extracted text from PDFs to structure the ratings."""
#     lines = ratings_text.split("\n")
#     overall_rating = None
#     score = None
#     graded_outcomes = {}

#     grading_outcomes = {"inadequate", "requires improvement", "good", "outstanding"}

#     for i, line in enumerate(lines):
#         line = re.sub(r"\s+", " ", line).strip()

#         # overall rating
#         if "Overall rating" in line:
#             overall_rating = line.split("Overall rating")[-1].strip()

#         # numerical score as %
#         score_match = re.search(r"\b(\d+)/(\d+)\b", line)
#         if score_match and score is None:
#             try:
#                 numerator, denominator = map(int, score_match.groups())
#                 if denominator > 0:
#                     score = round((numerator / denominator) * 100, 2)
#             except ValueError:
#                 print(f"⚠️ Error parsing score in: {line}")

#     cleaned_lines = [re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()]

#     for line in cleaned_lines:
#         match = re.match(r"^[PR]?\s*(\d+\.\d+)\s(.+?)\s(\w+)$", line)
#         if match:
#             category_name = match.group(2).strip()
#             grade = match.group(3).capitalize()

#             if grade.lower() in grading_outcomes:
#                 graded_outcomes[category_name] = grade

#     return {
#         # Note: need to review/improve consistency on these (case, space/underscore)
#         "LA_name": la_name,  # cleaned 
#         "LA_ref": la_ref,
#         "Score_%": score if score else "N/A", # % being the only special char we leave/dont clean in headers
#         "Overall Rating": overall_rating,
#         "publication_date": publication_date,  
#         "Report URL": report_url,
#         **graded_outcomes
#     }


def correct_column_names(extracted_columns):
    """
    Correct known mis-extracted column names dynamically.

    Args:
        extracted_columns (list): List of column names extracted from a report.

    Returns:
        dict: A dictionary mapping incorrect column names to corrected ones (only for present columns).
    """
    fix_column_mappings = {
        "Partners hips and services": "Partnerships and services",
        "Outofcourt disposal policy and provision": "Out-of-court disposal policy and provision"
    }
    
    return {col: fix_column_mappings[col] for col in extracted_columns if col in fix_column_mappings}


def parse_ratings(report_url, ratings_text, la_ref, la_name, publication_date):
    """Parse extracted text from PDFs to structure the ratings."""
    lines = ratings_text.split("\n")
    overall_rating = None
    score = None
    graded_outcomes = {}

    grading_outcomes = {"inadequate", "requires improvement", "good", "outstanding"}

    for i, line in enumerate(lines):
        line = re.sub(r"\s+", " ", line).strip()

        # Extract overall rating
        if "overall rating" in line.lower(): 
            overall_rating = line.split("Overall rating")[-1].strip()

        # Fix grading outcome by init letter match (as cannot be sure where mis-placed spacing will be)
        if overall_rating:
            first_letter = overall_rating[0].upper()  # Get first char
            grading_map = {
                "R": "Requires Improvement",
                "I": "Inadequate",
                "G": "Good",
                "O": "Outstanding"
            }
            overall_rating = grading_map.get(first_letter, overall_rating)  # Default original if no match

        # Extract numerical score as %
        score_match = re.search(r"\b(\d+)/(\d+)\b", line)
        if score_match and score is None:
            try:
                numerator, denominator = map(int, score_match.groups())
                if denominator > 0:
                    score = round((numerator / denominator) * 100, 2)
            except ValueError:
                print(f"⚠️ Error parsing score in: {line}")

    # Cleaned graded outcomes extraction
    cleaned_lines = [re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()]

    for line in cleaned_lines:
        match = re.match(r"^[PR]?\s*(\d+\.\d+)\s(.+?)\s(\w+)$", line)
        if match:
            category_name = match.group(2).strip()
            grade = match.group(3).capitalize()

            if grade.lower() in grading_outcomes:
                graded_outcomes[category_name] = grade

    # correction(s) for known mis-extracted/typo column names
    fix_column_mappings = {
        "Partners hips and services": "Partnerships and services",
        "Outofcourt disposal policy and provision": "Out-of-court disposal policy and provision"
    }
    corrected_outcomes = {fix_column_mappings.get(k, k): v for k, v in graded_outcomes.items()}

    # # Debug - corrected grading outcome
    # print(f"Debug: {la_name} - Fixed Overall Rating: {overall_rating}")

    record = {
        "la_name": la_name,  
        "la_ref": la_ref,
        "score_%": score if score else "N/A",
        "overall_rating": overall_rating,
        "publication_date": publication_date,
        "report_url": report_url,
        **corrected_outcomes  # outcome col headers
    }
    # record = {
    #     "LA_name": la_name,  
    #     "LA_ref": la_ref,
    #     "Score_%": score if score else "N/A",
    #     "Overall Rating": overall_rating,
    #     "publication_date": publication_date,
    #     "Report URL": report_url,
    #     **corrected_outcomes  # outcome col headers
    # }
    return record




def scrape_inspections():
    """Scrape reports, extract PDFs, and parse ratings."""
    ratings_data = []

    for la_ref, details in inspection_data.items():
        report_url = details["url"]
        la_name = clean_la_name(details["name"])  # cleaned
        publication_date = details.get("publication_date", "Unknown") 

        print(f"\nProcessing: {la_name} ({details['year']}) \n-> {report_url}")

        soup = get_soup(report_url)
        if not soup:
            continue

        # Find first valid PDF link (inspection reports always top/first)
        pdf_url = None

        for pdf_link in soup.find_all("a", href=True):
            if "inspection" in " ".join(pdf_link.text.lower().split()) and pdf_link["href"].endswith(".pdf"):
                pdf_url = pdf_link["href"]
                break  

        if not pdf_url:
            print(f"⚠️ No PDF found for: {la_name}")
            continue

        # Grab & parse ratings
        ratings_text = extract_ratings_from_pdf(pdf_url)
        if ratings_text != "Ratings page not found":
            parsed_data = parse_ratings(report_url, ratings_text, la_ref, la_name, publication_date)  
            ratings_data.append(parsed_data)
            print(f"Data extracted for {la_name} - Published on {publication_date}")

        time.sleep(2)  # Avoid request overload

    return ratings_data




def save_to_html(data_df, column_order, web_link_column="report_url"):
    """
    Exports data to an HTML table and saves as `index.html`.

    Args:
        data_df (DataFrame): The processed inspection ratings data.
        column_order (list): Desired column order.
        web_link_column (str): Column containing hyperlinks to reports.
    """
    # main page title & intro text
    page_title = "HMI Probation Youth Justice Inspections Summary (Pre-Release)"
    intro_text = (
        'Summarised outcomes of the most recent published HMI Youth Justice inspection reports by Local Authority.<br/>'
        'The summary and tool are in review/pre-release for feedback and towards suggested further development. <br/>'
        'Outcome gradings are temporarily replaced for readability with the following: "outstanding": 1, "good": 2, "requires improvement": 3, "inadequate": 4 <br/>'
        'It is not yet suitable for developing tools on top. E.g. We look to potentially merge some of the data columns and combine with other LA data/identifiers to increase the usefulness.<br/><br/>'
        'The below summary is available to <a href="hmi_youth_justice_inspection_ratings.csv">download here</a>; an expanded .xlsx version will replace this format.<br/>'
        'Read more about this tool/project '
        '<a href="https://github.com/data-to-insight/hmi-probation-youth-justice-scrape/blob/main/README.md">here</a>.'
    )

    disclaimer_text = (
        'Disclaimer:<br/>' 
        'This summary is built from scraped data directly from '
        '<a href="https://www.justiceinspectorates.gov.uk/hmiprobation/">HMI Probation</a> published PDF inspection reports. <br/>'
        'Due to report formatting variations and PDF encoding nuances, some extractions may be incomplete or inaccurate. '
        'Colleague feedback or corrections are welcomed. <a href="mailto:datatoinsight.enquiries@gmail.com?subject=Youth-Justice-Scrape-Tool">Contact us</a>.'
    )

    # fix col order if needed
    # data_df = data_df[column_order]

    # web links to clickable HTML hyperlinks
    if web_link_column in data_df.columns:
        base_url_to_remove = "https://www.justiceinspectorates.gov.uk/hmiprobation/inspections/"
        data_df[web_link_column] = data_df[web_link_column].apply(
            lambda x: f'<a href="{x}">{x.replace(base_url_to_remove, "")}</a>' 
            if isinstance(x, str) and x.startswith("http") else x
        )

    # in web version la ref is just clutter. the same is visible in the url anyway. 
    if 'la_ref' in data_df.columns:
        data_df.drop(columns=['la_ref'], inplace=True)

    # Avoid NaN's being visible in the front-end/html table
    data_df = data_df.apply(lambda x: x.fillna("").infer_objects(copy=False) if x.dtype == "object" else x)
    # tidy up string case just for the web
    # data_df = data_df.apply(lambda x: x.astype(str).str.title() if x.dtype == "object" else x)
    data_df["la_name"] = data_df["la_name"].astype(str).str.title()

    # ratings/outcomes mapping
    rating_mapping = {
        "outstanding": 1,
        "good": 2,
        "requires improvement": 3,
        "inadequate": 4
    }
    # apply outcomes mapping to all cols EXCEPT 'overall_rating' 
    # doing this only to improve readability on html summary until we can reduce num of cols
    columns_to_update = [col for col in data_df.columns if col != "overall_rating"]
    data_df[columns_to_update] = data_df[columns_to_update].apply(lambda col: 
        col.str.lower().replace(rating_mapping, regex=True) if col.dtype == "object" else col
    )

    # # Switch on only if using horizontal headings
    # # Col header abbr for HTML summary
    # column_abbreviation_mapping = {
    #     "publication_date": "publication",
    #     "implementation_and_delivery": "impl_and_delivery",
    #     "governance_and_leadership": "govern_and_leader",
    #     "partnerships_and_services": "partners_and_services",
    #     "information_and_facilities": "info_and_facilities",
    #     "outofcourt_disposal_policy_and_provision": "oocourt_policy_provision",
    #     "resettlement_policy_and_provision": "resettle_policy_provision"
    # }
    # data_df = data_df.rename(columns=column_abbreviation_mapping)

    # last updated visible page timestamp
    adjusted_timestamp_str = (datetime.now() + timedelta(hours=1)).strftime("%d %B %Y %H:%M")

    la_name_index = list(data_df.columns).index("la_name") + 1              # Convert to 1-based index
    report_url_index = list(data_df.columns).index("report_url") + 1        #
    overall_rating_index = list(data_df.columns).index("overall_rating") + 1    #

    # generate HTML content
    html_content = f"""
    <html>
    <head>
        <title>{page_title}</title>

        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                padding: 20px;
            }}
            .table-container {{
                overflow-x: auto; /* horiz scrolling if needed */
                max-width: 100%; /* table does not exceed the screen width */
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 10pt;
                table-layout: fixed; /* consistent column widths */
            }}
            table, th, td {{
                border: 1px solid #ddd;
            }}
            
            /* table headers and data */
            th, td {{
                padding: 5px;
                vertical-align: bottom; /* text aligns to the bottom */
            }}

            /* ONLY the first 5 columns */
            th:nth-child(-n+5), td:nth-child(-n+5) {{
                text-align: left;
            }}

            /* ONLY columns 6+ (index 5 onwards) */
            th:nth-child(n+6), td:nth-child(n+6) {{
                text-align: center;
            }}

            /*Header  */
            th {{
                background-color: #f2f2f2;
                font-size: 9pt;
                height: 120px; /* space for vertical text */
                white-space: normal;  /* Allow wrapping */
                word-wrap: break-word;
                overflow-wrap: break-word;
                vertical-align: bottom; /* headers are at the bottom edge */
            }}

            /* vertical rotation ONLY to headers AFTER the 5th column */
            th:nth-child(n+6) {{
                writing-mode: vertical-rl;  /* vertical text rotation */
                transform: rotate(180deg);  /* text is upright */
                vertical-align: bottom;
                width: 60px; /* space for the text */
                height: auto; /* height adjust naturally */
                padding: 10px 5px; /*bspace at lower header edge */
            }}

            /* fixed width for vertical header columns */
            td:nth-child(n+6), th:nth-child(n+6) {{
                width: 60px; /* Match header width */
                max-width: 60px;
            }}

            /* flexible width for 'report_url' column */
            td:nth-child({{report_url_index}}), th:nth-child({{report_url_index}}) {{
                white-space: nowrap; /* Prevent wrapping */
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 300px; /* Set reasonable limit */
            }}

            /* 'overall_rating' adapts but can wrap */
            td:nth-child({{overall_rating_index}}), th:nth-child({{overall_rating_index}}) {{
                white-space: normal; /* Allow text wrapping */
                word-wrap: break-word;
                max-width: 120px;
            }}

            /* fixed width for 'la_name' column */
            td:nth-child({{la_name_index}}), th:nth-child({{la_name_index}}) {{
                width: 170px;
            }}
        </style>


    </head>
    <body>
        <h1>{page_title}</h1>
        <p>{intro_text}</p>
        <p>{disclaimer_text}</p>
        <p><b>Summary last updated: {adjusted_timestamp_str}</b></p>
        <div>
    """

## Style block if not wrapping data / e.g. if deciding to re-map|abbreviate headers
        # <style>
        #     body {{
        #         font-family: Arial, sans-serif;
        #         margin: 20px;
        #         padding: 20px;
        #     }}
        #     table {{
        #         width: 100%;
        #         border-collapse: collapse;
        #         font-size: 10pt;
        #     }}
        #     table, th, td {{
        #         border: 1px solid #ddd;
        #     }}
        #     th, td {{
        #         padding: 5px;
        #         text-align: left;
        #     }}
            # th {{
            #     background-color: #f2f2f2;

            #     white-space: normal;  /* Allow wrapping */
            #     word-wrap: break-word; /* Words break */
            #     overflow-wrap: break-word; /* Wider browser support */
            #     font-size: 9pt;  
            #     max-width: 150px; 
            # }}
        #     }}
        # </style>
    

    # df to HTML table
    html_content += data_df.to_html(escape=False, index=False)

    # Close HTML
    html_content += "\n</div>\n</body>\n</html>"


    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ Youth Justice Inspections summary saved as `index.html`")



structured_data_df = pd.DataFrame(scrape_inspections())

# print(f"Pre-cleaned headers: {structured_data_df.columns}") # debug

# clean headers
structured_data_df.columns = (
    structured_data_df.columns
    .str.strip()  # leading/trailing spaces
    .str.replace(r"\s+", " ", regex=True)  # multiple spaces to single space
    .str.replace(r"[^\w\s%]", "", regex=True)  # rem special chars but keep %
    .str.replace(" ", "_", regex=True)  # spaces to underscores
    .str.replace("-", "_", regex=True)  # hyphens to underscores
    .str.replace(" ", "", regex=True)  # quash remaining spaces
    .str.lower()  # lowercase
)




# needs additional testing/verification
# making the asssumption here that if all the graded cols are unused, it's not an inspection report
existing_cols = structured_data_df.columns.intersection([
    'governance_and_leadership', 'staff', 'partnerships_and_services',
    'information_and_facilities', 'assessment', 'planning',
    'implementation_and_delivery', 'reviewing',
    'out_of_court_disposal_policy_and_provision',
    'resettlement_policy_and_provision', 'policy_and_provision',
    'joint_working'
])   
if not existing_cols.empty:  # avoid dropping if no columns match
    structured_data_df.dropna(subset=existing_cols, how='all', inplace=True)

structured_data_df.to_csv("hmi_youth_justice_inspection_ratings.csv", index=False)
print("Data saved to hmi_youth_justice_inspection_ratings.csv")


column_order = [
    'la_name', 'la_ref', 'score_%', 'overall_rating', 'publication_date', 'report_url',
    'governance_and_leadership', 'staff', 'partnerships_and_services',
    'information_and_facilities', 'assessment', 'planning',
    'implementation_and_delivery', 'reviewing',
    'out_of_court_disposal_policy_and_provision',
    'resettlement_policy_and_provision', 'policy_and_provision',
    'joint_working'
]


# create output/published single page
save_to_html(structured_data_df, column_order)