import glob
import os
import subprocess
import sys
from datetime import date, timedelta

cwd = os.getcwd()
path = os.getcwd() + "/Sources/BHUVAN"
script_path = cwd + "/Sources/BHUVAN/scripts/transformer.py"


for year in range(2021, 2022, 2023):
    print(year)
    year = str(year)
    for month in [
        "01",
    ]:
        files = glob.glob(
            path
            + "data/tiffs/removed_watermarks/"
            + "cuml_"
            + year
            + "_watermarkremoved"
            + "*.tif"
            # path + "data\\tiffs\\removed_watermarks\\tiffs\\" + year + "_??_" + month + "*.tif"
        )

        if len(files) == 0:
            print(f"No files for the month {month}")
            continue
        else:
            print(f"Number of images {month}:", len(files))
            subprocess.call(["python3", script_path, year, month])
