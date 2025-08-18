import pandas as pd
import numpy as np
import glob
import geopandas as gpd
import datetime
import os


root = os.getcwd()

#Function to drop columns
def drop_columns(df, cols_to_drop):
    cols_to_drop = []
    for col in df.columns:
    # Check if all values are NaN
        if df[col].isna().all():
            cols_to_drop.append(col)
    # Additionally, check if the column is numeric and all values are exactly zero
        elif pd.api.types.is_numeric_dtype(df[col]) and (df[col] == 0).all():
            cols_to_drop.append(col)
            cols_to_drop.extend([col for col in df.columns if df[col].nunique(dropna=False) == 1])
    df.drop(columns=cols_to_drop, inplace=True)
    return df



# Tests for verification
'''
hc_geocoded = pd.read_csv(root + r'/Sources\HPSDMA\data\losses-and-damages\Loss Data\hc_geocoded.csv')
hc_dist_gc = hc_geocoded.loc[hc_geocoded['district_best'] == 'bilaspur']


# Filter by Monsoon 2023
hc_dist_gc['incidentdate'] = pd.to_datetime(hc_dist_gc['incidentdate'], format='%d-%m-%Y', errors='coerce')
hc_dist_gc = hc_dist_gc.loc[(hc_dist_gc['incidentdate'] >= '2023-07-01') & (hc_dist_gc['incidentdate'] <= '2023-08-31')]
hc_dist_gc['amount'].sum() # 63

'''


# geocoding_function

import os
import re
import pandas as pd
from difflib import SequenceMatcher
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore")


def clean_text(text):
    """Utility to clean and lower-case a string."""
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text)).lower().strip()


def build_mappings(villages_df):
    """
    Build useful mappings from the villages dataframe.
      - district_candidates: unique cleaned district names from 'dtname'
      - village_to_district: maps cleaned village name (from VILNAM_SOI) to dtname
      - subdistrict_to_district: maps cleaned subdistrict name (from sdtname) to dtname.
        (If multiple rows exist, the first encountered is used.)
    """
    # Candidate districts
    district_candidates = villages_df['dtname'].dropna().unique().tolist()
    district_candidates = [clean_text(d) for d in district_candidates]

    village_to_district = {}
    for idx, row in villages_df.iterrows():
        village = clean_text(row.get('VILNAM_SOI', ''))
        district = row.get('dtname', '').strip()
        if village and village not in village_to_district:
            village_to_district[village] = district

    subdistrict_to_district = {}
    for idx, row in villages_df.iterrows():
        subdistrict = clean_text(row.get('sdtname', ''))
        district = row.get('dtname', '').strip()
        if subdistrict and subdistrict not in subdistrict_to_district:
            subdistrict_to_district[subdistrict] = district

    return district_candidates, village_to_district, subdistrict_to_district


def fuzzy_match(text, candidates):
    """
    Returns a sorted list of (candidate, score) tuples for the input text compared against
    a list of candidate strings using SequenceMatcher.
    """
    scores = []
    for candidate in candidates:
        score = SequenceMatcher(None, text, candidate).ratio()
        scores.append((candidate, score))
    return sorted(scores, key=lambda x: x[1], reverse=True)


def geotag_district(ungeo_df, villages_df, threshold=0.80, conflict_margin=0.05):
    """
    For each record in the ungeocoded dataset, assign a district.
    
    Process:
      1. Attempt direct matching using the 'district_name' column against candidate districts (dtname).
      2. If the direct match is missing or its score is below the threshold, build a fallback string
         from ['circle_name', 'block_name', 'division_name', 'location'] and try:
           a. Fuzzy match against candidate villages (VILNAM_SOI).
           b. If that fails, fuzzy match against candidate subdistricts (sdtname).
         In either fallback, return the corresponding district (dtname) using mappings.
         
      If the top two candidates are nearly equal (within conflict_margin), record an alternative.
    
    The function adds two new columns to ungeo_df:
        - 'district_best'
        - 'district_alternative'
    """
    # Build mappings and candidate lists
    district_candidates, village_to_district, subdistrict_to_district = build_mappings(villages_df)
    candidate_villages = list(village_to_district.keys())
    candidate_subdistricts = list(subdistrict_to_district.keys())

    district_best_list = []
    district_alt_list = []

    for idx, row in tqdm(ungeo_df.iterrows(), total=ungeo_df.shape[0], desc="Geotagging District"):
        # Step 1: Direct District Matching
        district_input = clean_text(row.get('district_name', ''))
        best_match = ""
        alt_match = ""
        best_score = 0.0

        if district_input:
            matches = fuzzy_match(district_input, district_candidates)
            if matches:
                best_candidate, best_score = matches[0]
                if best_score >= threshold:
                    best_match = best_candidate  # already cleaned
                    if len(matches) > 1:
                        second_candidate, second_score = matches[1]
                        if second_score >= threshold * 0.9 and (best_score - second_score) < conflict_margin:
                            alt_match = second_candidate

        # Step 2: Fallback Matching if needed
        if not best_match or best_score < threshold:
            fallback_parts = []
            for col in ['circle_name', 'block_name', 'division_name', 'location']:
                val = row.get(col, '')
                if pd.notnull(val) and str(val).strip():
                    fallback_parts.append(str(val))
            fallback_text = clean_text(" ".join(fallback_parts))

            fallback_best = ""
            fallback_alt = ""
            fallback_score = 0.0
            if fallback_text:
                village_matches = fuzzy_match(fallback_text, candidate_villages)
                if village_matches:
                    best_village, fallback_score = village_matches[0]
                    if fallback_score >= threshold:
                        fallback_best = village_to_district.get(best_village, "")
                        if len(village_matches) > 1:
                            second_village, second_score = village_matches[1]
                            if second_score >= threshold * 0.9 and (fallback_score - second_score) < conflict_margin:
                                fallback_alt = village_to_district.get(second_village, "")
                # If no good village match, try subdistrict names.
                if not fallback_best and fallback_text:
                    subd_matches = fuzzy_match(fallback_text, candidate_subdistricts)
                    if subd_matches:
                        best_subd, fallback_score = subd_matches[0]
                        if fallback_score >= threshold:
                            fallback_best = subdistrict_to_district.get(best_subd, "")
                            if len(subd_matches) > 1:
                                second_subd, second_score = subd_matches[1]
                                if second_score >= threshold * 0.9 and (fallback_score - second_score) < conflict_margin:
                                    fallback_alt = subdistrict_to_district.get(second_subd, "")
            best_match = fallback_best
            alt_match = fallback_alt

        district_best_list.append(best_match)
        district_alt_list.append(alt_match)

    ungeo_df['district_best'] = district_best_list
    ungeo_df['district_alternative'] = district_alt_list
    return ungeo_df


def geotag_subdistrict(ungeo_df, villages_df, threshold=0.80, conflict_margin=0.05, narrow_by_district=True):
    """
    For each record in the ungeocoded dataset, assign a subdistrict.
    
    Process:
      1. Primary Matching:  
         Use the 'sub_district_name' field to fuzzy-match against candidate subdistrict names (from 'sdtname').
      2. Fallback Matching:  
         If the primary match is insufficient (score below threshold), combine
         ['block_name', 'circle_name', 'division_name', 'location'] to build fallback text and match against
         candidate village names (from 'VILNAM_SOI'). If a good match is found, return the subdistrict
         corresponding to that village.
         
      Optionally, if narrow_by_district is True and the record has a matched district (in 'district_best'),
      the candidate list is filtered to only include villages/subdistricts from that district.
      
      Two new columns are added:
         - 'subdistrict_best'
         - 'subdistrict_alternative'
    """
    best_subd_list = []
    alt_subd_list = []

    for idx, row in tqdm(ungeo_df.iterrows(), total=ungeo_df.shape[0], desc="Geotagging Subdistrict"):
        # Optionally narrow the candidate pool by the matched district.
        matched_district = str(row.get('district_best', '')).strip()
        if matched_district and narrow_by_district:
            sub_df = villages_df[villages_df['dtname'].str.strip().str.lower() ==
                                   clean_text(matched_district)]
        else:
            sub_df = villages_df.copy()

        # Build candidate lists
        candidate_subd = sub_df['sdtname'].dropna().unique().tolist()
        candidate_subd = [clean_text(s) for s in candidate_subd]

        village_to_subd = {}
        # Mapping: clean village name --> subdistrict (sdtname)
        for i, r in sub_df.iterrows():
            village = clean_text(r.get('VILNAM_SOI', ''))
            subd = r.get('sdtname', '').strip()
            if village and subd and village not in village_to_subd:
                village_to_subd[village] = subd
        candidate_villages = list(village_to_subd.keys())

        # Primary matching using sub_district_name
        primary_input = clean_text(row.get('sub_district_name', ''))
        best_primary = ""
        alt_primary = ""
        primary_score = 0.0

        if primary_input:
            matches = fuzzy_match(primary_input, candidate_subd)
            if matches:
                best_candidate, primary_score = matches[0]
                if primary_score >= threshold:
                    best_primary = best_candidate
                    if len(matches) > 1:
                        second_candidate, second_score = matches[1]
                        if second_score >= threshold * 0.8 and (primary_score - second_score) < conflict_margin:
                            alt_primary = second_candidate

        # Fallback matching using other columns against village names
        fallback_parts = []
        for col in ['block_name', 'circle_name', 'division_name', 'location']:
            val = row.get(col, '')
            if pd.notnull(val) and str(val).strip():
                fallback_parts.append(str(val))
        fallback_input = clean_text(" ".join(fallback_parts))

        best_fallback = ""
        alt_fallback = ""
        fallback_score = 0.0
        if fallback_input:
            village_matches = fuzzy_match(fallback_input, candidate_villages)
            if village_matches:
                best_village, fallback_score = village_matches[0]
                if fallback_score >= threshold:
                    best_fallback = village_to_subd.get(best_village, "")
                    if len(village_matches) > 1:
                        second_village, second_score = village_matches[1]
                        if second_score >= threshold * 0.9 and (fallback_score - second_score) < conflict_margin:
                            alt_fallback = village_to_subd.get(second_village, "")
        # Decision logic for subdistrict selection.
        if primary_score >= threshold:
            chosen = best_primary
            alternate = alt_primary
        elif fallback_score >= threshold:
            chosen = best_fallback
            alternate = alt_fallback
        else:
            chosen = ""
            alternate = ""

        best_subd_list.append(chosen)
        alt_subd_list.append(alternate)

    ungeo_df['subdistrict_best'] = best_subd_list
    ungeo_df['subdistrict_alternative'] = alt_subd_list
    return ungeo_df

'''
def load_data():
    """
    Loads the ungeocoded dataset and the villages dataset.
    Update the file paths as needed.
    """
    ungeo_path = r"path_to_ungeocoded_file.csv"   # <-- Replace with your actual file path
    village_path = r"D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\HP\flood-data-ecosystem-Himachal-Pradesh\Maps\HP_VILLAGES.csv"      # <-- Replace with your actual file path
    villages_df = pd.read_csv(village_path)
    ungeo_df = pd.read_csv(ungeo_path)
    
    return ungeo_df, villages_df
'''

def geotag_tehsil_by_name(ungeo_df, tehsil_shp_path,
                          tehsil_name_field='TEHSIL',
                          object_id_field='object_id',
                          threshold=0.65, conflict_margin=0.05):
    # 1) load the tehsil table
    tehsil_gdf = gpd.read_file(tehsil_shp_path)
    # clean the names for fuzzy matching
    tehsil_gdf['clean'] = tehsil_gdf[tehsil_name_field].apply(clean_text)

    # build two dicts: clean → name, and clean → object_id
    name_map = dict(zip(tehsil_gdf['clean'], tehsil_gdf[tehsil_name_field]))
    id_map   = dict(zip(tehsil_gdf['clean'], tehsil_gdf[object_id_field]))

    candidates = list(name_map.keys())

    best_names    = []
    best_ids      = []
    alt_names     = []
    alt_ids       = []

    for _, row in ungeo_df.iterrows():
        txt = clean_text(row.get('subdistrict_best', ''))

        # defaults
        best_name = ""
        best_id   = np.nan
        alt_name  = ""
        alt_id    = np.nan

        if txt:
            matches = fuzzy_match(txt, candidates)
            if matches:
                # top match
                cand, score = matches[0]
                best_name = name_map[cand]
                best_id   = id_map[cand]

                # optional runner-up if close
                if len(matches) > 1 and (matches[0][1] - matches[1][1]) < conflict_margin:
                    alt_cand, _ = matches[1]
                    alt_name    = name_map[alt_cand]
                    alt_id      = id_map[alt_cand]

        best_names.append(best_name)
        best_ids.append(best_id)
        alt_names.append(alt_name)
        alt_ids.append(alt_id)

    # sanity check
    assert len(best_names) == len(ungeo_df)

    # assign four new columns
    ungeo_df['tehsil_best']           = best_names
    ungeo_df['tehsil_best_object_id'] = best_ids
    #ungeo_df['tehsil_alt']            = alt_names
    #ungeo_df['tehsil_alt_object_id']  = alt_ids

    return ungeo_df

def main():
    """
    Main function that runs the complete workflow - filtering and geotagging.
    
    Process:
      1. District geotagging: Fill in missing or ambiguous district info.
      2. Subdistrict geotagging: Optionally narrowed by the matched district.
      
    The output is saved to a CSV file with the new fields:
        - district_best, district_alternative,
        - subdistrict_best, subdistrict_alternative.
    """
    india_district = pd.read_csv(root + '/Sources\HPSDMA\data\losses-and-damages\Loss Data\keys_identifiers\districts_2.csv')
    district = india_district.loc[india_district['StateCode']==2]
    district = district.rename(columns={'DistrictId':'district_id','DistrictName':'district_name'})
    india_subdistrict = pd.read_csv(root + r'/Sources\HPSDMA\data\losses-and-damages\Loss Data\keys_identifiers\st_sub-district.csv')
    him_dist = district['district_id'].unique().tolist()
    subdistrict = india_subdistrict.loc[india_subdistrict['districtid'].isin(him_dist)]
    subdistrict = subdistrict.loc[subdistrict['status'] == 'Active']
    disaster_events = pd.read_csv(root+'/Sources\HPSDMA\data\losses-and-damages\Raw Data\extracted_tables\dbo.app_disaster_main.csv')
    disaster_types = pd.read_csv(root+'/Sources\HPSDMA\data\losses-and-damages\Raw Data\extracted_tables\dbo.DisasterType.csv')

    india_district = pd.read_csv(root + r'/Sources\HPSDMA\data\losses-and-damages\Loss Data\keys_identifiers\districts_2.csv')
    district = india_district.loc[india_district['StateCode']==2]
    district = district.rename(columns={'DistrictId':'district_id','DistrictName':'district_name'})

    # Filter by flood events
    flood_event_ids = [1]#,1002,2020]
    flood_events = disaster_events.loc[disaster_events['disaster_type_id'].isin(flood_event_ids)]
    #disaster_merged = pd.merge(disaster_keys[['disaster_id','incidentdate']],disaster_types[[]])

 
    cattle = pd.read_csv(r'D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\Deployment\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\losses-and-damages\Raw Data\extracted_tables\dbo.app_cattle_loss.csv')

    cattle_master = cattle.loc[cattle['disaster_id'].isin(flood_events['disaster_id'])]
    cattle_merged = cattle_master.merge(flood_events[['disaster_id','incidentdate']], on="disaster_id", how="left")
    #cattle_merged = cattle_master.merge(disaster_events[['disaster_id','incidentdate']], on="disaster_id", how="left")

    cattle_cleaned = drop_columns(cattle_merged, [])
    cattle_cleaned = cattle_cleaned.drop(columns={'entry_by','entry_date','ip_addr'})
    cattle_district = cattle_cleaned.merge(district[['district_id','district_name']], on='district_id',how='left')
    cattle_subdistrict = cattle_district.merge(subdistrict[['sub_district_name','sub_districtCode']], left_on='sub_district_id',right_on='sub_districtCode',how='left')
    cattle_subdistrict = cattle_subdistrict.loc[cattle_subdistrict['status'] == 'Active']
    columns_to_sum = ['MilchlostB','MilchlostS','DraughtlostC','DraughtlostCalf']
    cattle_subdistrict[columns_to_sum] = (
        cattle_subdistrict[columns_to_sum]
        .apply(pd.to_numeric, errors='coerce')
        .fillna(0)
    )

    # 3. Now sum across columns
    cattle_subdistrict['total_livestock_loss'] = (
        cattle_subdistrict[columns_to_sum]
        .sum(axis=1)
    )    
    ungeo_df = cattle_subdistrict

    # Load datasets
    #ungeo_df, villages_df = load_data()
    village_path = root+ r"/Maps\HP_VILLAGES.csv"      # <-- Replace with your actual file path
    villages_df = pd.read_csv(village_path)

    # District geotagging
    ungeo_df = geotag_district(ungeo_df, villages_df, threshold=0.68, conflict_margin=0.05)

    # Subdistrict geotagging – set narrow_by_district as needed (True or False)
    ungeo_df = geotag_subdistrict(ungeo_df, villages_df, threshold=0.6, conflict_margin=0.05, narrow_by_district=True)

    # tagging tehsil by 
    tehsil_shp = root + r'/Maps/hp_tehsil_final.geojson'
    ungeo_df = geotag_tehsil_by_name(ungeo_df, tehsil_shp)
    print(ungeo_df.columns)

    # Save output (update the file path)
    output_path = root + r"/Sources\HPSDMA\data\losses-and-damages\Loss Data\flood_losses\cattle_flood_geocoded.csv"  # <-- Update with desired output file path
    ungeo_df.to_csv(output_path, index=False)

    # Print summary statistics
    total_records = ungeo_df.shape[0]
    no_district = ungeo_df[ungeo_df['district_best'] == ""].shape[0]
    no_subdistrict = ungeo_df[ungeo_df['subdistrict_best'] == ""].shape[0]
    print(f"Total records processed: {total_records}")
    print(f"Records with no district match: {no_district}")
    print(f"Records with no subdistrict match: {no_subdistrict}")


if __name__ == '__main__':
    main()



