import os

import geopandas as gpd
import pandas as pd
import rasterio
import rasterstats

path = os.getcwd()

admin_bdry_gdf = gpd.read_file("<administrative_boundary_file_path>")

dem_raster = rasterio.open(path + "/Sources/NASADEM/data/NASADEM_DEM_30.tif")
dem_raster_array = dem_raster.read(1)

mean_dicts = rasterstats.zonal_stats(
    admin_bdry_gdf.to_crs(dem_raster.crs),
    dem_raster_array,
    affine=dem_raster.transform,
    stats=["mean"],
    nodata=dem_raster.nodata,
    geojson_out=True,
)
dfs = []
for rc in mean_dicts:
    dfs.append(pd.DataFrame([rc["properties"]]))

dem_zonal_stats_df = pd.concat(dfs).reset_index(drop=True)
dem_zonal_stats_df = dem_zonal_stats_df.rename(columns={"mean": "elevation_mean"})

slope_raster = rasterio.open(path + "/Sources/NASADEM/data/NASADEM_SLOPE_30.tif")
slope_raster_array = slope_raster.read(1)

mean_dicts = rasterstats.zonal_stats(
    admin_bdry_gdf.to_crs(slope_raster.crs),
    slope_raster_array,
    affine=slope_raster.transform,
    stats=["mean"],
    nodata=slope_raster.nodata,
    geojson_out=True,
)
dfs = []
for rc in mean_dicts:
    dfs.append(pd.DataFrame([rc["properties"]]))

slope_zonal_stats_df = pd.concat(dfs).reset_index(drop=True)
slope_zonal_stats_df = slope_zonal_stats_df.rename(columns={"mean": "slope_mean"})

zonal_stats_df = pd.merge(
    dem_zonal_stats_df,
    slope_zonal_stats_df[["TEHSIL", "slope_mean"]],
    on="TEHSIL",
)

zonal_stats_df.to_csv(
    path + "/Sources/NASADEM/data/variables/slope_elevation.csv", index=False
)
