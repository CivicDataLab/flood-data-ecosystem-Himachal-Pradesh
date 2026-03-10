import pandas as pd
import glob

# Path to the monthly_tenders folder
folder = 'Sources/TENDERS/data/monthly_tenders/'

# Get all CSV files in the folder
csv_files = glob.glob(folder + '*.csv')

total_count = 0
accepted_count = 0
all_dfs = []

for file in csv_files:
    try:
        df = pd.read_csv(file)
        all_dfs.append(df)
        total_count += len(df)
        if 'Status' in df.columns:
            accepted_count += (df['Status'] == 'Accepted-AOC').sum()
    except Exception as e:
        print(f'Error reading {file}: {e}')

# Concatenate all DataFrames and save to file
if all_dfs:
    combined_df = pd.concat(all_dfs, ignore_index=True)
    combined_df.to_csv('Sources/TENDERS/data/all_tenders.csv', index=False)
    print(f'Saved concatenated data to all_tenders.csv')

print(f'Total number of tenders (all files): {total_count}')
print(f'Total number of tenders with Status="Accepted-AOC": {accepted_count}')
