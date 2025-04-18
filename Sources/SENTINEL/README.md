# Sentinel-2
Sentinel-2 is a wide-swath, high-resolution, multi-spectral imaging mission supporting Copernicus Land Monitoring studies, including the monitoring of vegetation, soil and water cover, as well as observation of inland waterways and coastal areas. Check this [link](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED#description) for more details.

**Variables extracted from the source:** 

1. `mean-ndvi`: Mean Normalised Difference Vegetation Index (NDVI) value for the revenue circle
2. `mean-ndbi`: Mean Normalised Difference Building Index (NDBI) value for the revenue circle


## Project Structure
- `scripts` : Contains the scripts used to obtain the data
    - `sentinel.py`: Calculates mean NDVI and NDBI indices for each sub district in Himachal Pradesh for a given time range
- `data`: Contains datasets generated using the scripts

![Alt text](<docs/IDS-DRR ETL SENTINEL.jpg>)


