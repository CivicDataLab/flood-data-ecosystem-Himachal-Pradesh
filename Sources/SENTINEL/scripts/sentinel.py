import os
from datetime import datetime, timedelta

import ee
import geemap
import geopandas as gpd
import rasterio
from utils import maskS2clouds, zonal_stats_choropleths

cwd = os.getcwd()

# Initialize Google Earth Engine.
service_account = "<service_account>"  # Add service account.
credentials = ee.ServiceAccountCredentials(
    service_account,
    f"{cwd}/<secret.env>",  # Add json with service account credentials.
)
ee.Initialize(credentials)


def sentinel(context) -> None:
    """
    Downloads and processes Sentinel-2 imagery for a specified region and time period.

    Args:
        context (dict): Dictionary containing the following keys:
            - "state_name" (str): Name of the state ("Assam", "Odisha", or "Himachal Pradesh").
            - "date_from" (str): Start date in the format "YYYY-MM-DD".
            - "date_to" (str): End date in the format "YYYY-MM-DD".
            - "admin_bdry1" (str): Path to the state boundary shapefile.
            - "admin_bdry2" (str): Path to the administrative boundary shapefile.

    Raises:
        ValueError: If an invalid state name is provided or if the conversion of the shapefile to an Earth Engine object fails.
        Exception: If the download of images or the conversion of shapefiles fails.

    Returns:
        None
    """
    date_from = context.get("date_from", "")
    date_to = context.get("date_to", "")
    state_name = context.get("state_name", "")
    admin_bdry1 = context.get("admin_bdry1", "")
    admin_bdry2 = context.get("admin_bdry2", "")
    date_start = datetime.strptime(date_from, "%Y-%m-%d").replace(day=1)
    date_end = datetime.strptime(date_to, "%Y-%m-%d")
    while date_start < date_end:
        # Calculate the first day of the next month (date_end)
        next_month = date_start + timedelta(days=32)
        date_end_current = next_month.replace(day=1)
        # Convert the first day of the next month to a formatted date string
        date_end_str = date_end_current.strftime("%Y-%m-%d")
        date_start_str = date_start.strftime("%Y-%m-%d")

        print("Downloading data for {} - {}".format(date_start_str, date_end_str))

        if state_name.lower() == "assam":
            rc_shp_path = admin_bdry2
            rc_gdf = gpd.read_file(rc_shp_path)
            object_id = "object_id"
            state_boundary = admin_bdry1
        elif state_name.lower() == "odisha":
            rc_shp_path = admin_bdry2
            rc_gdf = gpd.read_file(rc_shp_path)
            object_id = "id"
            state_boundary = admin_bdry1
        elif state_name.lower() == "himachal pradesh":
            rc_shp_path = admin_bdry2
            rc_gdf = gpd.read_file(rc_shp_path)
            object_id = "TEHSIL"
            state_boundary = admin_bdry1
        else:
            raise ValueError("Invalid State.")
        # assam_rcs = ee.FeatureCollection("projects/ee-idsdrr/assets/assam_rc_180")

        try:
            state_boundary = geemap.shp_to_ee(state_boundary)
            if state_boundary is None:
                raise ValueError(
                    "Conversion of shapefile to Earth Engine object failed."
                )
            geometry = state_boundary.geometry()
        except Exception as e:
            print(f"Error converting shapefile: {e}")

        # Get GEE Image Collection
        sentinel = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        # Filter the image collection
        sentinel_filtered = (
            sentinel.filter(ee.Filter.date(date_start_str, date_end_str))
            .filter(ee.Filter.bounds(geometry))
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        )  # Filter for images that have less then 20% cloud coverage.

        # Apply cloud mask
        sentinel_filtered_cloud_masked = sentinel_filtered.map(maskS2clouds)
        # Choose median image
        sentinel_median = sentinel_filtered_cloud_masked.median()

        ndvi = sentinel_median.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndbi = sentinel_median.normalizedDifference(["B11", "B8"]).rename("ndbi")

        print("-------NDVI Image-------------")
        path = cwd + "/Sources/SENTINEL/data/NDVI/tifs"
        # Check if the directory exists
        if not os.path.exists(path):
            # Create the directory if it doesn't exist
            os.makedirs(path)

        geemap.ee_export_image(
            ndvi,
            filename=path + "/ndvi_{}.tif".format(date_start_str),
            scale=250,
            region=geometry,
            file_per_band=True,
        )

        print("-------NDBI Image-------------")
        path = cwd + "/Sources/SENTINEL/data/NDBI/tifs"
        # Check if the directory exists
        if not os.path.exists(path):
            # Create the directory if it doesn't exist
            os.makedirs(path)

        geemap.ee_export_image(
            ndbi,
            filename=path + "/ndbi_{}.tif".format(date_start_str),
            scale=250,
            region=geometry,
            file_per_band=True,
        )

        try:
            ndvi_raster = rasterio.open(
                cwd
                + "/Sources/SENTINEL/data/NDVI/tifs"
                + f"/ndvi_{date_start_str}.ndvi.tif"
            )
            ndbi_raster = rasterio.open(
                cwd
                + "/Sources/SENTINEL/data/NDBI/tifs"
                + f"/ndbi_{date_start_str}.ndbi.tif"
            )
        except Exception as e:
            print(f"Download failed for month: {date_start_str}", e)
            date_start = date_end_current
            continue

        print("-------NDVI Stats-------------")
        ndvi_rc_df, ndvi_rc_gdf = zonal_stats_choropleths(
            rc_gdf, object_id, ndvi_raster
        )
        ndvi_rc_df.head()

        path = cwd + "/Sources/SENTINEL/data/variables/NDVI"
        # Check if the directory exists
        if not os.path.exists(path):
            # Create the directory if it doesn't exist
            os.makedirs(path)

        ndvi_rc_df.to_csv(
            path + "/ndvi_subdis_{}.csv".format(date_start_str), index=False
        )
        print("File saved to:", path + f"/ndvi_subdis_{date_start_str}.csv")

        print("-------NDBI Stats-------------")
        ndbi_rc_df, ndbi_rc_gdf = zonal_stats_choropleths(
            rc_gdf, object_id, ndbi_raster
        )

        path = cwd + "/Sources/SENTINEL/data/variables/NDBI"
        # Check if the directory exists
        if not os.path.exists(path):
            # Create the directory if it doesn't exist
            os.makedirs(path)

        ndbi_rc_df.to_csv(
            path + "/ndbi_subdis_{}.csv".format(date_start_str), index=False
        )
        print("File saved to:", path + f"/ndbi_subdis_{date_start_str}.csv")
        date_start = date_end_current


if __name__ == "__main__":
    sentinel(
        context={
            "state_name": "Himachal Pradesh",
            "date_from": "<start_date>",
            "date_to": "<end_date>",
            "admin_bdry1": "<state_boundary_path>",
            "admin_bdry2": "<boundary_path>",
        },
    )
