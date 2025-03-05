# FOI Whisper Network 
### FOI scrape tool(s) and related data processing 

## Conceptual/initial problem brief
FOI requests submitted to local authorities by both private individuals and organisations are increasing in frequency. Though valid, the short time-frame requirements, and added overheads on already stretched (data)teams comes at a time-cost to those affected; more so where data data reporting is a small or single person team or that time is allocated on a part-time basis only.   

Is it possible to succinctly monitor submitted FOI requests? If yes, it might be possible to (pre-emptively) develop coded responses to these for open use or gain insights from patterns of requested data. This potentially allowing solutions/efforts to be shared collaboratively between impacted local authorities. Should LA colleagues wish, Analysts could also upload/submit both requests they have recieved directly, and|or their responses to recieved FOI requests. 

In combination with deployment of the [Standard Safeguarding Dataset (SSD)] (https://github.com/data-to-insight/ssd-data-model), where data points for Child Social Care are both known and standardised, it would be possible to codify FOI solutions that could be distributed|utilised by any LA who has received the same or similar FOI request(s). By accessing a central FOI resource within the SSD Git repo, analysts could save hours of unpredictable time and effort. 

Published: [data-to-insight.github.io/foi-scrape-tool](https://data-to-insight.github.io/foi-scrape-tool/)

## Project| Repo File Overview

tbc

--- 

## mkdocs commands ref
* `mkdocs serve --help`     - see list of options including the below
* `mkdocs build --clean`    - build docs site
* `mkdocs serve`            - live-reload docs server
* `mkdocs serve -a 127.0.0.1:8080`  - serve on new port if blocked

* `mkdocs gh-deploy`        - push to Gitpage front-end(public)

* `pkill mkdocs`            - kill any running MkDocs process
* `lsof -i :8000`           - kill running 
* `kill -9 12345`           - kill process (Replace 12345 with PID)


## Features  

- Scrapes **details from FOI requests** from public source(s)   
- Outputs data in **structured HTML amd CSV for download**  
- **Setup and execution automated** via `./setup.sh`  
- **Pre-release** – still in development, feedback welcome!  

## Setup & Running  

To install dependencies and run the scraper, run (might need file permissions set but details in the file header):  

```bash
./setup.sh
```

This will:  

- Install required **Python libraries**  
- Run scraper to **Collect/process data**  
- Generate an **Current summary to markdown**  

---

## Future Adaptability  

The scraper **currently focuses on whattheyknow wite**, but could be **extended** to cover other available sources, such as:  

- **tbc**  

---

## Feedback & Contributions  

This tool is still **in early dev/alpha**, and changes/improvements are ongoing. If you encounter any issues, incorrect data extraction, or have suggestions, feel free to:  

- **Open an issue** in this GitHub repo  (not yet available)
- **Email us** at [datatoinsight.enquiries@gmail.com](mailto:datatoinsight.enquiries@gmail.com)  
