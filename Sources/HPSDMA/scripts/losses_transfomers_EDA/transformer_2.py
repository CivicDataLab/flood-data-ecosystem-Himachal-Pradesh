import pandas as pd
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────

root = Path.cwd()
flood_loss_folder = root / r"Sources\HPSDMA\data\losses-and-damages\Loss Data\flood_losses"
output_folder     = root / r"Sources\HPSDMA\data\variables\losses-and-damages"
output_folder.mkdir(parents=True, exist_ok=True)

columns_map = {
    'municipal':  ['internalwatersupply','electricwires','Electricpoles','Roadlength','streetlights'],
    'health':     ['health_centres_lost','health_amount'],
    'cattle':     ['total_livestock_loss'],
    'human':      ['person_dead','person_major_injury','person_missing'],
    'education':  ['schools_damaged','economic_loss'],
    'structure':  ['structure_lost'],
    'economic':   ['economic_loss','amount'],
}

LAKH_THRESHOLD = 10000

# Pre-create a container for each indicator
all_indicators = set().union(*columns_map.values())
indicator_data = {ind: [] for ind in all_indicators}

# ─── FIND INPUT FILES ────────────────────────────────────────────────────────────

files = sorted(flood_loss_folder.glob("*_flood_geocoded*.csv"))
print(f"🔎 Found {len(files)} files in {flood_loss_folder}")
if not files:
    raise SystemExit("❌ No files found – check your folder path or pattern.")

# ─── PROCESS EACH LOSS-TYPE ─────────────────────────────────────────────────────

for path in files:
    prefix = path.stem.split('_')[0].lower()
    if prefix not in columns_map:
        print(f"⚠️  skipping unknown prefix '{prefix}' in {path.name}")
        continue

    inds = columns_map[prefix]
    print(f"▶️  {path.name} → indicators: {inds}")
    df = pd.read_csv(path).rename(
        columns={'tehsil_best_object_id':'object_id'}
    )

    if 'object_id' not in df or 'incidentdate' not in df:
        print(f"⚠️  {path.name} missing required columns; skipping.")
        continue

    # keep only object_id, date + those indicators
    keep = ['object_id','incidentdate'] + inds
    df = df.loc[:, [c for c in keep if c in df.columns]].copy()

    # parse date → YYYY_MM
    df['incidentdate'] = pd.to_datetime(df['incidentdate'],
                                        format='%d-%m-%Y', dayfirst=True)
    df['timeperiod']   = df['incidentdate'].dt.strftime('%Y_%m')

    # normalize financials in lakhs
    for col in inds:
        if col in {'amount','economic_loss'}:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            mask = df[col].between(0, LAKH_THRESHOLD)
            df.loc[mask, col] *= 100_000

    # aggregate by object_id + timeperiod
    agg = (
        df
        .groupby(['object_id','timeperiod'], as_index=False)[inds]
        .sum()
    )

    # stash each indicator’s rows for later
    for col in inds:
        tmp = agg[['object_id','timeperiod',col]].copy()
        indicator_data[col].append(tmp)

# ─── WRITE OUT MONTHLY FILES ────────────────────────────────────────────────────

for ind, chunks in indicator_data.items():
    if not chunks:
        continue

    # combine all loss-types for this indicator
    df_all = pd.concat(chunks, ignore_index=True)

    # make sure its folder exists
    ind_folder = output_folder / ind
    ind_folder.mkdir(parents=True, exist_ok=True)

    # for each month, write a file
    for tp, grp in df_all.groupby('timeperiod'):
        out_path = ind_folder / f"{ind}_{tp}.csv"
        # we only need object_id + the indicator value
        grp[['object_id', ind]].to_csv(out_path, index=False)
        print(f"✅ Wrote {out_path}")
