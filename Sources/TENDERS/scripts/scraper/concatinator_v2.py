# save as concat_monthly_tenders.py
import pandas as pd
import os
import glob
import re
from collections import defaultdict

# === FINAL schema (exact order & names you asked for) ===
FINAL_COLS = [
    'Tender ID','tender_externalreference','tender_title','Work Description','Tender Category','Tender Type',
    'Form of contract','Product Category','Is Multi Currency Allowed For BOQ','Allow Two Stage Bidding',
    'Independent External Monitor/Remarks','Published Date','Pre Bid Meeting Date','Bid Validity(Days)',
    'Should Allow NDA Tender','Allow Preferential Bidder','Payment Mode','Bid Opening Date',
    'Organisation Chain','location','Pincode','No of Bids Received','Tender Value in ₹','Bidder Name',
    'Awarded Value','Status','Contract Date :','Department'
]

# Raw headers that often appear → canonical RAW name (pre-rename)
HEADER_VARIANTS = {
    # Rupee symbol variants
    'Tender Value in â‚¹': 'Tender Value in ₹',
    'Tender Value in Rs': 'Tender Value in ₹',
    'Tender Value in INR': 'Tender Value in ₹',
    'Tender Value (INR)': 'Tender Value in ₹',

    # Spacing / punctuation / spelling variants
    'Independent External Monitor / Remarks': 'Independent External Monitor/Remarks',
    'Independent External Monitor-Remarks': 'Independent External Monitor/Remarks',
    'No. of Covers ': 'No. of Covers',
    'No of Covers': 'No. of Covers',
    'Organisation  Chain': 'Organisation Chain',
    'Organization Chain': 'Organisation Chain',
    'Work Location': 'Location',
    'Published Date': 'Publish Date',
    'Bid Opening  Date': 'Bid Opening Date',

    # Contract Date variants
    'Contract Date': 'Contract Date :',
    'Contract Date:': 'Contract Date :',
    'Contract  Date :': 'Contract Date :',
}

def normalize_cols(cols):
    """Trim, collapse internal whitespace, map known variants, and normalize 'Unnamed' blanks."""
    out = []
    for c in cols:
        c2 = re.sub(r'\s+', ' ', str(c).strip())
        c2 = HEADER_VARIANTS.get(c2, c2)
        if c2 == '' or re.match(r'^Unnamed', c2, flags=re.I):
            c2 = 'Unnamed'
        out.append(c2)
    return out

def make_unique(names):
    """Ensure column names are unique by suffixing duplicates."""
    seen = defaultdict(int)
    unique = []
    for n in names:
        if seen[n]:
            unique.append(f"{n}__dup{seen[n]}")
        else:
            unique.append(n)
        seen[n] += 1
    return unique

# Raw → Final rename map (AFTER normalization)
RAW_TO_FINAL_RENAME = {
    'Tender Reference Number': 'tender_externalreference',
    'Title': 'tender_title',
    'Publish Date': 'Published Date',
    'No. of Covers': 'No of Bids Received',
    'Location': 'location',
    # Everything else already matches the final names
}

# Minimum raw set we expect to try building the final file
RELEVANT_RAW_COLS = {
    'Tender ID','Tender Reference Number','Title','Work Description','Tender Category','Tender Type',
    'Form of contract','Product Category','Is Multi Currency Allowed For BOQ','Allow Two Stage Bidding',
    'Independent External Monitor/Remarks','Publish Date','Pre Bid Meeting Date','Bid Validity(Days)',
    'Should Allow NDA Tender','Allow Preferential Bidder','Payment Mode','Bid Opening Date',
    'Organisation Chain','Location','Pincode','No. of Covers','Tender Value in ₹','Bidder Name',
    'Awarded Value','Status','Contract Date :'
}

# Columns that may be missing in some files but required in final output
FILL_IF_MISSING = [
    'Bidder Name','Awarded Value','Status','Contract Date :'
]

for year in range(2024, 2026):
    ystr = str(year)

    for month in range(1, 13):
        mstr = str(month).zfill(2)
        folder = f"{ystr}_{mstr}"

        print(folder)
        path = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'scripts', 'scraper',
                            'scraped_recent_tenders', folder)
        out_dir = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'data', 'monthly_tenders')

        csvs = glob.glob(os.path.join(path, '*.csv'))
        print('Number of tenders: ', len(csvs))
        if not csvs:
            continue

        dfs = []
        for csv_path in csvs:
            try:
                df = pd.read_csv(csv_path, engine='python')
            except Exception:
                df = pd.read_csv(csv_path, engine='python', encoding='utf-8', encoding_errors='ignore')

            # Normalize + dedupe headers (prevents InvalidIndexError on concat)
            cols = normalize_cols(df.columns)
            if pd.Index(cols).duplicated().any():
                dup_names = pd.Series(cols)[pd.Index(cols).duplicated()].tolist()
                if dup_names:
                    print(f"  - Dedup headers in {os.path.basename(csv_path)}: {set(dup_names)}")
            df.columns = make_unique(cols)

            # Keep all columns; we’ll map/select after concat
            dfs.append(df)

        # Safe concat
        master_df = pd.concat(dfs, ignore_index=True)

        # If 'Tender ID' missing entirely, skip this month
        if 'Tender ID' not in master_df.columns:
            print('Error: "Tender ID" column not found in any file for', folder)
            continue

        # Drop rows without Tender ID
        master_df = master_df.dropna(subset=['Tender ID'])

        # First, try to project the relevant raw columns (create empties for missing ones)
        for c in RELEVANT_RAW_COLS:
            if c not in master_df.columns:
                master_df[c] = pd.NA

        # Now rename raw → final
        master_df = master_df.rename(columns=RAW_TO_FINAL_RENAME)

        # Department derived from Organisation Chain
        if 'Organisation Chain' in master_df.columns:
            master_df['Department'] = master_df['Organisation Chain']
        else:
            master_df['Department'] = pd.NA

        # Ensure any required-but-missing columns exist
        for c in FILL_IF_MISSING:
            if c not in master_df.columns:
                master_df[c] = pd.NA

        # Final projection & order
        missing_final = [c for c in FINAL_COLS if c not in master_df.columns]
        for c in missing_final:
            master_df[c] = pd.NA

        master_df = master_df[FINAL_COLS]

        # Write
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'{folder}_tenders.csv')
        master_df.to_csv(out_path, index=False)
