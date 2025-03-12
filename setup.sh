#!/bin/bash
# chmod +x setup.sh 

echo "🚀 Set up & running FOI Scrape..."

# # virtual env
# python3 -m venv venv

# # virtual environment (for Linux/Mac)
# source venv/bin/activate

# Upgrade
pip install --upgrade pip

# required dependencies
pip install -r requirements.txt
# pip install --upgrade --force-reinstall -r requirements.txt
# /home/codespace/.python/current/bin/python -m pip install -r requirements.txt


echo "✅ Done setup. Now running scrape script..."

# run scrape
python foi-csc-scrape-tool.py

# echo "🎉 Scrape process finished Whoohoo!"