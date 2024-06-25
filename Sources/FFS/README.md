# Scraping Waterlevel data from Flood forecast Stations (FFS)

The Central Water Commission (CWC) collects and maintains water level data from Flood forecast stations. This data is made available by the CWC here - [Link](https://ffs.india-water.gov.in/). 

There are two divisions in Himachal Pradesh. FFS stations are majorly distributed in these divisions
1. Snow Hydrology Division(SHD), Shimla (SHDSIM)
2. Upper Yamuna Division(UYD), New Delhi (UYDDEL)


## Project Directory:
1. `scripts`: Contains codes to scrape data from FFS.
    - `stations.py`: To create a geojson for all the stations in a state
    - `scraper.py`: To scrape data from CWC
    - `transformer.py`: To calculate variables
2. `data`: Contains all datasets used and produced for this source.