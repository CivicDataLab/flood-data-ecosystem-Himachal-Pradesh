import os
import pandas as pd
from pathlib import Path
import re
import glob

main_directory = Path.cwd() / r'Sources'
print(main_directory)


# Iterate through all folders and sub-folders
for root, dirs, files in os.walk(main_directory):
    root_path = Path(root)
    print(root_path)
    
    if 'variables' in root_path.parts:
        csv_files = list(root_path.glob('*.csv'))  # No need for '**/*.csv'
        dfs = []
        for csv in csv_files:
            #csv = csv.resolve()
            if any(folder in str(csv.parts) for folder in ['BHARATMAPS', 'GCN250', 'NASADEM', 'NERDRR', 'ANTYODAYA','WRIS','HRVA']):
                timeperiod = ''
                file_name = csv.stem
            elif any(folder in str(csv.parts) for folder in ['WORLDPOP']):#, 'WRIS']):
                year_match = re.findall(r'\d{4}', csv.name)
                if year_match:
                    timeperiod = year_match[0]
                    file_name = csv.stem[:-5]
                
            elif any("SENTINEL" in str(parent) for parent in csv.parents):
                date_match = re.findall(r'\d{4}-\d{2}-\d{2}', csv.name)
                if date_match:
                    timeperiod = date_match[0][:-3].replace('-', '_')
                    file_name = csv.stem
            
            else:
                date_match = re.findall(r'\d{4}_\d{2}', csv.name)
                if date_match:
                    timeperiod = date_match[0]
                    file_name = csv.stem[:-8]
                
            print("file: ", file_name)
            df = pd.read_csv(csv)
            df['timeperiod'] = timeperiod
            dfs.append(df)

        if dfs:  # Check if there are any dataframes to concatenate
            master_df = pd.concat(dfs)
            master_df.to_csv(main_directory / f'master/{file_name}.csv', index=False)


# IMD
path = main_directory / 'IMD/data/rain/csv'
csvs = glob.glob(str(path / '*.csv'))
dfs = []
for csv in csvs:
    month = re.findall(r'\d{4}_\d{2}', csv)[0]
    df = pd.read_csv(csv)
    df['timeperiod'] = month
    dfs.append(df)

master_df = pd.concat(dfs)
master_df = master_df.rename(columns={'max': 'max_rain', 'mean':'mean_rain', 'sum':'sum_rain'})
master_df.to_csv(main_directory / 'master/rainfall.csv', index=False)

# BHUVAN
path = main_directory / 'BHUVAN/data/variables/inundation_pct'
csvs = glob.glob(str(path / '*.csv'))
dfs = []
for csv in csvs:
    month = re.findall(r'\d{4}_\d{2}', csv)[0]
    df = pd.read_csv(csv)
    df['timeperiod'] = month
    dfs.append(df)

master_df = pd.concat(dfs)
master_df.to_csv(main_directory / 'master/inundation.csv', index=False)

# NRSC
path = main_directory / 'NRSC/data/variables/runoff'
csvs = glob.glob(str(path / '*.csv'))
dfs = []
for csv in csvs:
    month = re.findall(r'\d{4}_\d{2}', csv)[0]
    df = pd.read_csv(csv)
    df['timeperiod'] = month
    dfs.append(df)

master_df = pd.concat(dfs)
master_df.to_csv(main_directory / 'master/runoff.csv', index=False)
