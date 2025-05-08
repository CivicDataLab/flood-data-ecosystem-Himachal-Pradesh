import subprocess
import os
from datetime import date, timedelta

cwd = os.getcwd() +r"/HP/flood-data-ecosystem-Himachal-Pradesh"
script_path = cwd+r'/Sources/TENDERS/scripts/scraper/scraper_HP_recent_tenders_tender_status.py'

for year in range(2022,2025):
    year = str(year)
    for month in range(1,12):        
        month=str(month)
        print(year+'_'+month)
        subprocess.call([f"C:\\Users\\saura\\anaconda3\\envs\\cdl-env\\python.exe", script_path, year, month])

        #subprocess.call([f"D:\CivicDataLab_IDS-DRR\IDS-̥DRR_Github\cdl\python.exe", script_path, year, month])

