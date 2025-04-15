# NHP National Hydrological Modelling System
Under National Hydrology Project (NHP), the National level hydrological modeling framework is prepared in the Variable Infiltration Capacity (VIC) model towards water balance computation. The model computes evapotranspiration, surface runoff, soil moisture, base flow, and energy fluxes on a daily basis for entire India at 5.5 km grid resolution. Check this [link](https://bhuvan.nrsc.gov.in/nhp/webgis-vic/map) to explore the data source.

**Variables extracted from the source:**

1. `Mean_Daily_Runoff`: The average daily runoff, aggregated over a month in mm
2. `Sum_Runoff`: Total monthly runoff in mm.
3.  `Peak_Runoff`: Max daily runoff in mm.


## Folder Structure

- `data`: Contains datasets generated using the scripts.
    - `tiffs`: Contains flood inundation maps of a given day after geo-referencing.


- `scripts` : Contains the scripts used to obtain the data