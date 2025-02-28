#!/bin/bash
# chmod +x setup.sh 

echo "🚀 Set up & running HMI Youth Justice Scrape..."

# # virtual env
# python3 -m venv venv

# # virtual environment (for Linux/Mac)
# source venv/bin/activate

# Upgrade
pip install --upgrade pip

# required dependencies
pip install -r requirements.txt

echo "✅ Done. running scrape script..."

# run scrape
python hmi_youth_justice_inspection_scrape.py

echo "🎉 Scrape process finished!"