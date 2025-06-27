# Define the path to the folder containing the documents
import os
import pandas as pd
from pathlib import Path
from shutil import move
from dateutil import parser


# Define the path to the folder containing the CSV documents
folder_path = Path(r"D:\CivicDataLabs_IDS-DRR\IDS-DRR_Github\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\TENDERS\data\Himachal Pradesh Tender data-20240801T075249Z-001\Himachal Pradesh Tender data\hp_tenders_aoc_2023\final_csvs")

# Function to parse various datetime formats
def parse_date_time(date_str):
    if isinstance(date_str, str):
        try:
            # Attempt to parse the date using dateutil.parser
            parsed_date = parser.parse(date_str, dayfirst=True)
            return parsed_date.strftime('%d-%b-%Y')
        except (ValueError, OverflowError) as e:
            print(f"Error parsing date {date_str}: {e}")
            return None
    else:
        return None  # Handle non-string entries

# Iterate over each CSV file in the folder
for csv_path in folder_path.glob("*.csv"):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(csv_path)
    
    # Check if the "Status Updated On" column exists
    if "Status Updated On" in df.columns:
        # Apply the parsing function to the column
        df["Status Updated On"] = df["Status Updated On"].apply(parse_date_time)
        
        # Save the updated DataFrame back to the CSV file
        df.to_csv(csv_path, index=False)
        
    # Check if the "Contract Date :" column exists
    if "Contract Date :" in df.columns:
        # Extract the contract date from the first row (or adjust as needed)
        date_str = df["Contract Date :"].iloc[0]
        
        # Convert the date to yyyy_mm format
        parsed_date = parse_date_time(date_str)
        if parsed_date:
            folder_name = pd.to_datetime(parsed_date, format='%d-%b-%Y').strftime('%Y_%m')
            target_folder = folder_path / folder_name
            
            # Create the target folder if it doesn't exist
            target_folder.mkdir(exist_ok=True)
            
            # Move the CSV file to the target folder
            move(str(csv_path), str(target_folder / csv_path.name))

print("CSV files have been organized based on contract dates and updated dates.")