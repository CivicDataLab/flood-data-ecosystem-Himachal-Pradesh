import pandas as pd
import os
import glob
import datetime
import geopandas as gpd
import warnings
warnings.filterwarnings("ignore")

# --- Paths ---
variables_data_path = os.getcwd() + r'/Sources/master/'
print(variables_data_path)

# --- Base geometry ---
HP_sd = gpd.read_file(os.getcwd() + r'/Maps/hp_tehsil_final.geojson')

# --- Build full (object_id x month) frame ---
date_range = pd.date_range(start="2021-04-01", end="2025-06-30", freq='MS')
formatted_dates = [date.strftime('%Y_%m') for date in date_range]

dfs = []
for year_month in formatted_dates:
    df = HP_sd[['TEHSIL', 'object_id', 'dtcode11', 'tehsil_area', 'District']].copy()
    df.columns = ['TEHSIL', 'object_id', 'dtcode11', 'tehsil_area', 'district']
    df['timeperiod'] = year_month
    dfs.append(df)

master_df = pd.concat(dfs).reset_index(drop=True)
master_df['district_obj'] = master_df['object_id'].str.rsplit(pat='-', n=1).str[0]

# --- Monthly variables ---
monthly_variables = [
    'total_tender_awarded_value', 'Repair and Restoration_tenders_awarded_value',
    'LWSS_tenders_awarded_value', 'NDRF_tenders_awarded_value', 'SDMF_tenders_awarded_value',
    'WSS_tenders_awarded_value', 'Preparedness Measures_tenders_awarded_value',
    'Immediate Measures_tenders_awarded_value', 'Others_tenders_awarded_value',
    'rainfall', 'runoff', 'inundation', 'structure_lost', 'health_centres_lost', 'health_amount',
    'internalwatersupply', 'electricwires', 'Electricpoles', 'Roadlength', 'streetlights',
    'person_dead', 'person_major_injury', 'schools_damaged', 'economic_loss',
    'total_livestock_loss', 'relief_and_mitigation_sanction_value'
]

for variable in monthly_variables:
    variable_df = pd.read_csv(os.path.join(variables_data_path, f"{variable}.csv"))
    if variable == 'relief_and_mitigation_sanction_value':
        # district-level monthly → merge on district_obj + timeperiod
        variable_df = variable_df.rename(columns={'object_id': 'district_obj'})
        variable_df = variable_df.drop_duplicates(subset=['district_obj', 'timeperiod'])
        cols = ['district_obj', 'timeperiod']
        if variable in variable_df.columns:  # keep the metric if present
            cols.append(variable)
        master_df = master_df.merge(variable_df[cols], on=['district_obj', 'timeperiod'], how='left')
    else:
        # object_id-level monthly
        variable_df = variable_df.drop_duplicates(subset=['object_id', 'timeperiod'])
        cols = ['object_id', 'timeperiod']
        if variable in variable_df.columns:
            cols.append(variable)
        master_df = master_df.merge(variable_df[cols], on=['object_id', 'timeperiod'], how='left')

# --- Annual variables ---
master_df['year'] = master_df['timeperiod'].str[:4].astype(int)
annual_variables = ['mean_sex_ratio', 'sum_aged_population', 'sum_young_population', 'sum_population']

for variable in annual_variables:
    variable_df = pd.read_csv(os.path.join(variables_data_path, f"{variable}.csv"))
    variable_df = variable_df.rename(columns={'timeperiod': 'year'})
    # Ensure year is int if it looks numeric
    if variable_df['year'].dtype == object:
        with pd.option_context('mode.chained_assignment', None):
            variable_df['year'] = pd.to_numeric(variable_df['year'], errors='coerce').astype('Int64')
    keep_cols = ['object_id', 'year']
    if variable in variable_df.columns:
        keep_cols.append(variable)
    variable_df = variable_df[keep_cols].drop_duplicates(subset=['object_id', 'year'])
    master_df = master_df.merge(variable_df, on=['object_id', 'year'], how='left')

# --- One-time variables (STATIC) ---
onetime_variables = [
    'Schools', 'RailLengths', 'RoadLengths',
    'slope_elevation', 'antyodaya_variables',
    'drainage_density', 'distance_from_river', 'rural_vul'
]

def prepare_onetime_df(df: pd.DataFrame, master_cols) -> pd.DataFrame:
    """
    Keep only object_id + columns that are NOT already in master_df (avoid collisions).
    Drop any previous suffix leftovers and obvious non-feature keys.
    """
    df = df.copy()
    # Remove leftovers/keys that can collide or are not needed
    drop_exact = {'TEHSIL', 'District', 'district', 'dtcode11', 'tehsil_area',
                  'timeperiod', 'year', 'month'}
    df = df.drop(columns=[c for c in df.columns if c in drop_exact], errors='ignore')
    # Remove any _x/_y columns coming from previously saved merges
    df = df.loc[:, ~df.columns.str.endswith(('_x', '_y'))]
    # Ensure object_id exists
    if 'object_id' not in df.columns:
        raise ValueError("One-time variables file missing 'object_id' column.")
    # Keep only new feature columns (not already present in master_df) + object_id
    new_feats = [c for c in df.columns if c != 'object_id' and c not in master_cols]
    df = df[['object_id'] + new_feats]
    # Deduplicate per object
    df = df.drop_duplicates(subset=['object_id'])
    return df

for variable in onetime_variables:
    variable_df = pd.read_csv(os.path.join(variables_data_path, f"{variable}.csv"))
    variable_df = prepare_onetime_df(variable_df, master_df.columns)
    # Merge on object_id only, no suffixes
    master_df = master_df.merge(variable_df, on='object_id', how='left')

# --- Final tidy / imputations ---
# Drop columns if present
master_df = master_df.drop(columns=['district_obj'], errors='ignore')
master_df = master_df.drop(columns=['count_bhuvan_pixels', 'count_inundated_pixels'], errors='ignore')

# Rain/runoff imputations (group means by object_id)
for col in ['max_rain', 'mean_rain', 'sum_rain', 'Sum_Runoff', 'Peak_Runoff', 'Mean_Daily_Runoff']:
    if col in master_df.columns:
        master_df[col] = master_df[col].fillna(master_df.groupby('object_id')[col].transform('mean'))

# Antyodaya imputations (by district)
by_district_mean = ['block_nosanitation_hhds_pct', 'block_piped_hhds_pct', 'avg_electricity', 'net_sown_area_in_hac']
by_district_median = ['avg_tele']
for col in by_district_mean:
    if col in master_df.columns:
        master_df[col] = master_df[col].fillna(master_df.groupby('district')[col].transform('mean'))
for col in by_district_median:
    if col in master_df.columns:
        master_df[col] = master_df[col].fillna(master_df.groupby('district')[col].transform('median'))

# Fill remaining NaNs with 0
master_df = master_df.fillna(0)

# Remove any accidental suffix leftovers if any slipped through
master_df = master_df.loc[:, ~master_df.columns.str.endswith(('_x', '_y'))]

# Save
out_path = os.getcwd() + r'/Sources/MASTER_VARIABLES.csv'
master_df.to_csv(out_path, index=False)
print(master_df.shape, "-> saved to:", out_path)
