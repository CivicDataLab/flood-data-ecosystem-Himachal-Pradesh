import os
import subprocess
import timeit

from osgeo import gdal

gdal.DontUseExceptions()

path = os.getcwd() + "/flood-data-ecosystem-Himachal-Pradesh/Sources/BHUVAN"

date_strings = [
    "cuml_2021"
]  # Sample date for assam - "2023_07_07_18", HP - cuml_2021, Orissa - 2022_16_08 / 2022_18_08_18

# Specify the state information to scrape data for.
state_info = {"state": "Himachal-Pradesh", "code": "hp"}


for dates in date_strings:

    # Define your input and output paths
    input_xml_path = path + "/data/inundation.xml"
    output_tiff_path = path + f"/data/tiffs/{dates}.tif"

    layer_hp = "fld_cuml_2021_hp"
    state_code = "hp"
    url_hp = "https://bhuvan-ras2.nrsc.gov.in/mapcache"

    # Download the WMS(Web Map Sevice) layer and save as XML.
    command = [
        "gdal_translate",
        "-of",
        "WMS",
        f"WMS:{url_hp}?&LAYERS={layer_hp}&TRANSPARENT=TRUE&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&FORMAT=image%2Fpng&SRS=EPSG%3A4326&BBOX=75.289307,30.353916,79.562988,33.321349",
        f"{path}{state_info['state']}/data/inundation.xml",
    ]
    subprocess.run(command)

    # Specify the target resolution in the X and Y directions
    target_resolution_x = 0.0001716660336923202072
    target_resolution_y = -0.0001716684356881450775

    # Perform the warp operation using gdal.Warp()
    print("Warping Started")
    starttime = timeit.default_timer()

    gdal.Warp(
        output_tiff_path,
        input_xml_path,
        format="GTiff",
        xRes=0.0001716660336923202072,
        yRes=-0.0001716684356881450775,
        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
        callback=gdal.TermProgress_nocb,  # None #gdal.TermProgress,
    )

    print("Time took to Warp: ", timeit.default_timer() - starttime)
    print(f"Warping completed. Output saved to: {output_tiff_path}")
