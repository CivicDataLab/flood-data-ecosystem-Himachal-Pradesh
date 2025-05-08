import pandas as pd 
import numpy as np
import geopandas as gpd
import os

path = os.getcwd() +r'/HP/flood-data-ecosystem-Himachal-Pradesh'

# Load spatial data
blocks = gpd.read_file(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Administrative\block_admin.shp')  # Replace with your file
tehsils = gpd.read_file(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Maps\HP_IDS-DRR_shapefiles\hp_tehsil_final.geojson')
blocks = blocks.to_crs(epsg=7755)  # Replace with the EPSG code suitable for your region
tehsils = tehsils.to_crs(epsg=7755)

natural_vi = pd.read_csv(r"\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Natural Vulnerability Index Rural.csv")
human_vi = pd.read_csv(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Human Vulnerability Index - AllGroups.csv')
financial_vi = pd.read_csv(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Financial Vulnerability Index Rural - AllGroups.csv')
physical_vi = pd.read_csv(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Physical Vulnerability Index Rural-AllGroups.csv')
social_vi = pd.read_csv(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Social Vulnerability Index Rural - AllGroups.csv')
composite_vi = pd.read_csv(r'\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\Taru HRVA datasets\Rural Vulnerability\Composite Vulnerability Index - Rural.csv')

blocks = blocks.merge(natural_vi,on='FID0', how='left')
blocks = blocks.merge(human_vi,on='FID0', how='left')
blocks = blocks.merge(financial_vi,on='FID0', how='left')
blocks = blocks.merge(physical_vi,on='FID0', how='left')
blocks= blocks.merge(social_vi,on='FID0',how='left')
blocks = blocks.merge(composite_vi,on='FID0', how='left')

index_prefixes = ["NVIAll", "SVIAll", "CVIAll", "HVIAll","FVIAll","PVIAll"]
classes = {"02": 1, "24": 2, "46": 3, "68": 4, "810": 5}

for prefix in index_prefixes:
    # Filter columns for the current prefix
    prefix_columns = [col for col in blocks.columns if col.startswith(prefix)]
    
    # Calculate the composite value
    blocks[f"{prefix}_comp"] = sum(
        blocks[f"{prefix}{cls}"] * value for cls, value in classes.items()
    )

block_scores = blocks[['Block','DISTRICT','geometry','FID0','NVIAll_comp','SVIAll_comp','CVIAll_comp','HVIAll_comp','FVIAll_comp','PVIAll_comp']]

# Perform spatial overlay to get intersection areas
intersection = gpd.overlay(block_scores, tehsils, how='intersection')

# Calculate area of each intersection
intersection['area'] = intersection.geometry.area


block_areas = blocks[['FID0', 'geometry']]
block_areas['block_area'] = block_areas.geometry.area
intersection = intersection.merge(block_areas[['FID0', 'block_area']], on='FID0')
intersection['weight'] = intersection['area'] / intersection['block_area']

indexes = ['NVIAll_comp', 'SVIAll_comp','CVIAll_comp', 'HVIAll_comp', 'FVIAll_comp', 'PVIAll_comp']

for col in indexes:  # Columns to aggregate
    intersection[col] = intersection[col] * intersection['weight']

# Aggregate to tehsil level
tehsil_data = intersection.groupby('object_id')[indexes].sum()
tehsil_data = tehsil_data.reset_index()