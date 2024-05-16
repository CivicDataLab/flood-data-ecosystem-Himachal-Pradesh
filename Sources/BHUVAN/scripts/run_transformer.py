import glob
import os
import subprocess
from datetime import date, timedelta


import sys
print(sys.executable)

cwd = os.getcwd()
print(cwd)
path = os.getcwd() + "\\IDS-DRR-HP\\Sources\\BHUVAN\\Himachal-Pradesh\\"
script_path = cwd + "\\IDS-DRR-HP\\Sources\\BHUVAN\\scripts\\transformer.py"
python_path = cwd + "\\.conda\python.exe"
print(path)
for year in range(2021,2022,2023):
    print(year)
    year = str(year)
    for month in [
        "01",
    ]:
        files = glob.glob(
            path + "data\\tiffs\\removed_watermarks\\tiffs\\" + "cuml_"+ year + "_watermarkremoved" + "*.tif"
            #path + "data\\tiffs\\removed_watermarks\\tiffs\\" + year + "_??_" + month + "*.tif"
        )
        
        if len(files) == 0:
            print(f"No files for the month {month}")
            continue
        else:
            print(f"Number of images {month}:", len(files))
            subprocess.Popen([python_path, script_path, year, month], shell = True)
            
