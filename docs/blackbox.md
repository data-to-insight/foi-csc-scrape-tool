# FOI Scraping & Summarisation Process

## Overview
This process automates the collection, filtering, and summarisation of Freedom of Information (FOI) requests related to **Children’s Services**.  
It aggregates data from multiple sources, making it easier for analysts to track, compare, and with the future intention to enable more efficient response processes to FOI requests for Children's Social Care data.

## What This Process Does

**Scrapes FOI Requests**  

   - Extract public FOI request records from sources such as:  
     - [WhatDoTheyKnow.com](https://www.whatdotheyknow.com)   
     - Direct from Local Borough Councils web sites where available.
     - Direct(via email) from LA data/CSC team colleagues.  


**Filters and Cleans the Data**  

   - Retrieve request title, response status, submitted date, relevant authority/agency, and published response URL.  
   - Identify duplicate or related requests across local authorities.  
   - Remove irrelevant requests (e.g., from non-LA bodies such as schools, police, or government departments).  
   - Normalise and standardise data (e.g. authority names) to improve consistency.  
   - Extract key identifiers (FOI reference numbers) where available.  

**Aggregates FOIs**  

   - Counts how often each local authority receives requests related to Children’s Services (based on below search terms).  
   - Highlight requests that multiple authorities have received (indicating potential sector-wide trends).  
   - Structured output formats for analysis and use.  

**Outputs Data in Multiple Formats**  

   - **CSV File** → Expanded data for external analysis (`foi_requests_summary.csv`).  
   - **MkDocs Pages** → Limited data within integrated markdown pages for documentation and structured publishing.  

---

## Data collection

Collection methods vary depending on the source, with each platform publishing their own format/method/data.  
In general, the process searches published FOI records using predefined **search terms**. It extracts data directly from public FOI listings and refines/combines the results.  

**Current search terms being applied are:**  

- ```["looked after children", "children in need", "childrens social care", "childrens services"]```  
- ```["care leavers", "child fostering", "foster carer", "adoption"]```   
- ```["care order", "family support", "special educational needs"]```  


LA colleagues can assist by submitting suggestions for additional search terms where they observe that further relevant FOI requests are not currently being picked up from the source platforms. 

### Handling Different FOI Sources
**WhatDoTheyKnow.com**  

  - Search for FOI requests based on keywords.  
  - Extract request details from paginated search results.  
  - Identifies authority, request status, and response classification.  
  - Match FOI reference numbers where available.  
  
**Hastings Borough Council FOI Archive**  

  - Retrieve yearly FOI request records back to 2016.  
  - Extract request details from both summary pages and individual FOI entries.  
  - Match FOI reference numbers from structured headings.  

**Local Authority Submitted Data**  

  - Colleagues from various LAs can submit FOI details via CSV upload.  
  - These are merged with scraped data for a comprehensive dataset.  

---

## How the Data is Summarised
Once the FOI records are collected, they undergo some basic further processing:

**Authority-Level Aggregation**  

  - Counts FOIs per local authority.  
  - Flags requests that multiple LAs have received.  
  
**Cleaning and Formatting**  

For some of the web/dashboard outputs, it's necessary to reformat some of the shown data/structure.

- Convert long statuses (e.g., "Partially Successful") into shorter versions ("Partial").  
- Shorten column headings to improve readability in web tables.  
- Format request URLs into clickable active links so colleagues can access the FOIR context & detail.  


**Dynamic Data Presentation**  
  - Summarised pages show key FOI trends across LAs.  
  - Alternative view(s) offer a more detailed breakdown.  

---

## Potential use-cases
✅ **Saves Time** → Reduces the effort needed to locate and compare similar|sector FOI requests.  
✅ **Improves Consistency** → Standardises data across multiple sources for easier analysis.  
✅ **Identifies Trends** → Highlights sector-wide FOI topics that may require a coordinated response.  
✅ **Supports Collaboration** → Encourages local authorities to share data and insights.  
✅ **Enables sector-driven FOI response** → Integrated with the SSD, the potential for pre-developed, codified response solutions for data teams
---

## How to Contribute
Local authority colleagues can:

- **Report Errors** → If FOI entries don't display as expected or believed missing, send [feedback & corrections](mailto:datatoinsight@gmail.com?subject=FOI%20Feedback).  
- **Submit FOI Requests** → Add new FOI records to improve the dataset. Send details via [this submission link](mailto:datatoinsight@gmail.com?subject=FOI%20details%20to%20add&body=Authority-Name:%20%3Cla-name%3E%0AAuthority-Code:%20%3Cla-code%3E%0ARequest-Title:%20%3Crequest-title%3E).

By contributing, we can build a **shared FOI intelligence resource** that benefits all local authorities.

---

This summary provides a **high-level view** of what the process does and how it helps in managing FOI requests. 
