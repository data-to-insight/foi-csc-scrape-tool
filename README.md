# hmi-probation-youth-justice-scrape  

This repository contains a **scraper for HM Inspectorate of Probation Youth Justice inspection reports**, extracting structured data from published PDFs. The extracted data is compiled into a **summary dataset**, which is automatically updated and published as an HTML report. Note: We are reviewing with colleagues atm regarding how best to potentially combine historic/mis-matched grading columns to improve the summary output usefulness and display without compromising the expected gradings. 

## 🚀 Features  

- Scrapes **only Youth Justice inspection reports** from HMI Probation  
- Extracts **inspection ratings and outcomes** directly from PDF reports  
- Outputs data in **structured CSV and HTML formats**  
- **Setup and execution automated** via `./setup.sh`  
- **Alpha release** – still in development, feedback welcome!  

## 🔧 Setup & Running  

To install dependencies and run the scraper, run (might need permissions set but details in the file header):  

```bash
./setup.sh
```

## 🔧 Setup & Running  

This will:  

- ✅ Install required **Python libraries**  
- ✅ Run scraper to **Collect/process data**  
- ✅ Generate an **Current HTML summary**  

---

## 🔄 Future Adaptability  

The scraper **currently focuses on Youth Justice inspections**, but could be **extended** to cover other available report types, such as:  

- 📌 **Probation services**  
- 📌 **Joint Targeted Area Inspections (JTAI)**  
- 📌 **Serious Further Offence Reviews**  
- 📌 **Thematic reports**  

---

## 📢 Feedback & Contributions  

This tool is still **in early dev/alpha**, and improvements are ongoing. If you encounter any issues, incorrect data extraction, or have suggestions, feel free to:  

- 🛠 **Open an issue** in this GitHub repo  
- 📩 **Email us** at [datatoinsight.enquiries@gmail.com](mailto:datatoinsight.enquiries@gmail.com)  
