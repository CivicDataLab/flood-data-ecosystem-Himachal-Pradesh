import os
import time

import ee
import geemap
import geopandas as gpd
import pandas as pd
import rasterio
import rasterstats

cwd = os.getcwd()

# Initialize Google Earth Engine.
service_account = "<service_account>"  # Add service account.
credentials = ee.ServiceAccountCredentials(
    service_account,
    f"{cwd}/<secret.env>",  # Add json with service account credentials.
)
ee.Initialize(credentials)


def zonal_stats_choropleths(
    gdf,
    gdf_unique_id,
    raster,
    stats_list=["mean", "count"],
):
    """
    Calculates zonal statistics for given geographic data using a raster image and
    returns the results as both a DataFrame and GeoDataFrame.

    Args:
        gdf (GeoDataFrame): A GeoDataFrame containing the geographic features for which
                            zonal statistics are to be calculated.
        gdf_unique_id (str): The unique identifier column in the GeoDataFrame used for
                             merging the results.
        raster (rasterio.io.DatasetReader): A raster image opened with rasterio to be
                                            used for zonal statistics calculation.
        stats_list (list, optional): A list of statistical measures to calculate.
                                     Defaults to ["mean", "count"].

    Returns:
        tuple: A tuple containing:
            - DataFrame: A pandas DataFrame with the calculated statistics.
            - GeoDataFrame: A GeoDataFrame with the calculated statistics merged with
                            the original GeoDataFrame.
    """

    mean_dicts = rasterstats.zonal_stats(
        gdf.to_crs(raster.crs),
        raster.read(1),
        affine=raster.transform,
        stats=stats_list,
        nodata=raster.nodata,
        geojson_out=True,
    )

    dfs = []
    for rc in mean_dicts:
        dfs.append(pd.DataFrame([rc["properties"]]))

    zonal_stats_df = pd.concat(dfs).reset_index(drop=True)
    zonal_stats_gdf = pd.merge(
        gdf, zonal_stats_df[stats_list + [gdf_unique_id]], on=gdf_unique_id
    )
    zonal_stats_gdf = gpd.GeoDataFrame(zonal_stats_gdf)
    return zonal_stats_df, zonal_stats_gdf


def gcn250(context, admin_bdry1, admin_bdry2):
    """
    Processes zonal statistics for a specified state's administrative boundaries
    using Google Earth Engine (GEE) images and saves the results.

    Args:
        context (dict): A dictionary containing parameters for running the script.
                        Must include the key "state_name" which specifies the state
                        for which the script will run (e.g., "assam", "odisha",
                        "himachal pradesh").
        admin_bdry1 (str): File path to the shapefile (.shp) representing the
                           administrative boundary of the state.
        admin_bdry2 (str): File path to the shapefile (.shp) representing a lower-level
                           administrative boundary within the state (e.g., revenue circles,
                           subdistricts).

    Raises:
        ValueError: If an invalid state name is provided or if the shapefile conversion
                    to Earth Engine object fails.

    Returns:
        None
    """

    state_name = context.get("state_name", "")
    if state_name.lower() == "assam":
        rc_shp_path = admin_bdry2
        rc_gdf = gpd.read_file(rc_shp_path)
        object_id = "object_id"
        state_boundary_path = admin_bdry1
    elif state_name.lower() == "odisha":
        rc_shp_path = admin_bdry2
        rc_gdf = gpd.read_file(rc_shp_path)
        object_id = "id"
        state_boundary_path = admin_bdry1
    elif state_name.lower() == "himachal pradesh":
        rc_shp_path = admin_bdry2
        rc_gdf = gpd.read_file(rc_shp_path)
        object_id = "TEHSIL"
        state_boundary_path = admin_bdry1
    else:
        raise ValueError("Invalid State.")

    tic = time.perf_counter()

    # Get GEE Image Collection
    GCN250_Average = ee.Image("users/jaafarhadi/GCN250/GCN250Average")
    GCN250_Dry = ee.Image("users/jaafarhadi/GCN250/GCN250Dry")
    GCN250_Wet = ee.Image("users/jaafarhadi/GCN250/GCN250Wet")

    try:
        state_boundary = geemap.shp_to_ee(state_boundary_path)
        geometry = state_boundary.geometry()
        if state_boundary is None:
            raise ValueError("Conversion of shapefile to Earth Engine object failed.")
    except Exception as e:
        print(f"Error converting shapefile: {e}")

    print("------- Images -------------")
    path = cwd + "/Sources/GCN250/data"
    # Check if the directory exists
    if not os.path.exists(path):
        # Create the directory if it doesn't exist
        os.makedirs(path)

    geemap.ee_export_image(
        GCN250_Average,
        filename=path + "/GCN250_Average.tif",
        scale=250,
        region=geometry,
        file_per_band=True,
    )

    geemap.ee_export_image(
        GCN250_Dry,
        filename=path + "/GCN250_Dry.tif",
        scale=250,
        region=geometry,
        file_per_band=True,
    )

    geemap.ee_export_image(
        GCN250_Wet,
        filename=path + "/GCN250_Wet.tif",
        scale=250,
        region=geometry,
        file_per_band=True,
    )

    print("------- Stats-------------")
    gcn_avg_raster = rasterio.open(path + "/GCN250_Average.b1.tif")
    gcn_dry_raster = rasterio.open(path + "/GCN250_Dry.b1.tif")
    gcn_wet_raster = rasterio.open(path + "/GCN250_Wet.b1.tif")

    path = cwd + "/Sources/GCN250/data/variables"
    if not os.path.exists(path):
        # Create the directory if it doesn't exist
        os.makedirs(path)

    # AVERAGE
    gcn_rc_df, gcn_rc_gdf = zonal_stats_choropleths(rc_gdf, object_id, gcn_avg_raster)
    gcn_rc_df.to_csv(path + "/gcn250_average_rc.csv", index=False)

    # DRY
    gcn_rc_df, gcn_rc_gdf = zonal_stats_choropleths(rc_gdf, object_id, gcn_dry_raster)
    gcn_rc_df.to_csv(path + "/gcn250_dry_rc.csv", index=False)

    # WET
    gcn_rc_df, gcn_rc_gdf = zonal_stats_choropleths(rc_gdf, object_id, gcn_wet_raster)
    gcn_rc_df.to_csv(path + "/gcn250_wet_rc.csv", index=False)

    toc = time.perf_counter()
    print("Time Taken: {} seconds".format(toc - tic))
    return None


if __name__ == "__main__":
    gcn250(
        context={"state_name": "Himachal Pradesh"},
        admin_bdry1="<state_boundary_path>",
        admin_bdry2="<boundary_path>",
    )
