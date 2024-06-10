import os

import ee
import geemap

cwd = os.getcwd()

# Initialize Google Earth Engine.
service_account = "<service_account>"  # Add service account.
credentials = ee.ServiceAccountCredentials(
    service_account,
    f"{cwd}/<secret.env>",  # Add json with service account credentials.
)
ee.Initialize(credentials)

# Path to the administrative boundary shapefile.
state_boundary_path = cwd + "<administrative_boundary_shapefile_path>"
try:
    state_boundary = geemap.shp_to_ee(state_boundary_path)
    geometry = state_boundary.geometry()
    if state_boundary is None:
        raise ValueError("Conversion of shapefile to Earth Engine object failed.")
except Exception as e:
    print(f"Error converting shapefile: {e}")


# Get GEE Image
nasadem = ee.Image("NASA/NASADEM_HGT/001")

elevation = nasadem.select("elevation")
task = ee.batch.Export.image.toDrive(
    image=elevation.clip(geometry),
    region=geometry,
    description="NASADEM_DEM_30",
    folder="NASADEM",
    scale=30,
    maxPixels=1e13,
)
task.start()
print("Task ID:", task.id)


slope = ee.Terrain.slope(elevation)
task = ee.batch.Export.image.toDrive(
    image=slope.clip(geometry),
    region=geometry,
    description="NASADEM_SLOPE_30",
    folder="NASADEM",
    scale=30,
    maxPixels=1e13,
)
task.start()
print("Task ID:", task.id)
