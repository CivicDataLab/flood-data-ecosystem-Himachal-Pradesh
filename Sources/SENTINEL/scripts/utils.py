import geopandas as gpd
import pandas as pd
import rasterstats


# Function for Zonal Stats
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


# Function to mask clouds
def maskS2clouds(image):
    qa = image.select("QA60")

    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11

    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloudBitMask).eq(0)
    mask = mask.bitwiseAnd(cirrusBitMask).eq(0)

    return image.updateMask(mask).divide(10000)


# clip_image function clips the satellite image to our given area of interest
def clip_image(aoi):
    def call_image(image):
        return image.clip(aoi)

    return call_image
