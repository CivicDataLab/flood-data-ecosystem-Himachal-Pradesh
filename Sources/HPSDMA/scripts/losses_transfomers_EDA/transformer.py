import pandas as pd
from pathlib import Path
import os

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
root = Path.cwd()
print(root)
flood_loss_folder = Path(root, r'Sources\HPSDMA\data\losses-and-damages\Loss Data\flood_losses')

output_folder = Path(root,r'Sources\HPSDMA\data\variables\losses-and-damages'
)
output_folder.mkdir(parents=True, exist_ok=True)

municipal_columns  = ['internalwatersupply','electricwires','Electricpoles','Roadlength','streetlights']
health_columns     = ['centres_lost','amount']
cattle_columns     = ['MilchlostB','MilchlostS','DraughtlostC','DraughtlostCalf']
human_columns      = ['person_dead','person_major_injury','person_missing']
education_columns  = ['schools_damaged','economic_loss']
structure_columns  = ['structure_lost']
economic_columns   = ['economic_loss','amount']  # financial fields

columns_map = {
    'municipal': municipal_columns,
    'health':    health_columns,
    'cattle':    cattle_columns,
    'human':     human_columns,
    'education': education_columns,
    'structure': structure_columns,
    'economic':  economic_columns,
}

LAKH_THRESHOLD = 10000
# ─── DEBUG: list what you actually see ─────────────────────────────────────────
# 1) grab all CSVs matching the pattern
files = sorted(flood_loss_folder.glob("*_flood_geocoded*.csv"))
print(f"🔎 Looking in {flood_loss_folder}\n   Found {len(files)} files:")
for p in files:
    print("   •", p.name)

if not files:
    raise SystemExit("❌ No files found!  Check your folder path or filename pattern.")

# ─── PROCESS EACH FILE ─────────────────────────────────────────────────────────

for csv_path in files:
    # 2) derive a simple key from the filename
    #    e.g. "municipal_flood_geocoded.csv" → "municipal"
    prefix = csv_path.stem.split('_')[0].lower()
    if prefix not in columns_map:
        print(f"⚠️  Unknown prefix '{prefix}' in {csv_path.name}; skipping.")
        continue

    indicators = columns_map[prefix]
    print(f"▶️  Processing {csv_path.name} as '{prefix}' indicators: {indicators}")

    df = pd.read_csv(csv_path)

    # 3) rename if needed
    df = df.rename(columns={'tehsil_best_object_id': 'object_id'})

    # 4) check required cols
    if 'object_id' not in df or 'incidentdate' not in df:
        print(f"⚠️  {csv_path.name} missing object_id or incidentdate; skipping.")
        continue

    # 5) select only what we need
    keep = indicators + ['object_id','incidentdate']
    df = df[[c for c in keep if c in df.columns]].copy()

    # 6) parse date → timeperiod
    df['incidentdate'] = pd.to_datetime(df['incidentdate'], format='%d-%m-%Y', dayfirst=True)
    df['timeperiod']   = df['incidentdate'].dt.strftime('%Y_%m')

    # 7) normalize financial fields
    for col in indicators:
        if col in {'amount','economic_loss'}:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            mask = df[col].between(0, LAKH_THRESHOLD)
            df.loc[mask, col] *= 100_000

    # 8) aggregate and write out
    agg = df.groupby(['object_id','timeperiod'], as_index=False)[indicators].sum()
    out_file = output_folder / f"{prefix}_loss.csv"
    agg.to_csv(out_file, index=False)
    print(f"✅ Wrote {out_file}")

    

# ─── OPTIONAL: combine all into one ─────────────────────────────────────────────

# (repeat the debug for combined if desired)