# flood-data-ecosystem-Himachal-Pradesh
The repository contains codes to extract relevant datasets and the modelling approach used to calculate Risk Scores in Himachal Pradesh.

---

## Repository Structure

- **Maps/**: Contains geospatial data and map visualizations related to flood risk in Himachal Pradesh.
- **Sources/**: Includes raw data sources and scripts for data extraction pertinent to the project.
- **requirements.txt**: Lists the Python dependencies required to run the scripts in this repository.
- **CITATION.cff**: Provides citation information for referencing this repository in academic works.
- **LICENSE**: Details the licensing information for the repository.
- **README.md**: Offers an overview of the project, including its purpose and structure.

---


## Datasets

The repository includes scripts to extract and process various datasets essential for modeling flood risk in Himachal Pradesh. Below are some key datasets:

### Flood Procurement Data
- **[Flood Tenders Data](https://github.com/CivicDataLab/flood-data-ecosystem-Himachal-Pradesh/tree/main/Sources/TENDERS/data/flood_tenders)**:
  - Contains procurement data related to flood activities in Himachal Pradesh for the financial years 2019 to 2024.

- **[Monthly Procurement Data](https://github.com/CivicDataLab/flood-data-ecosystem-Himachal-Pradesh/tree/main/Sources/TENDERS/data/monthly_tenders)**:
  - Contains monthly procurement data for Himachal Pradesh from FY 2019 to 2024.

---

## Sources Directory Structure

### **data/**

The `data/` folder houses datasets essential for flood risk assessment and is organized as follows:

- **raw/**: Contains unprocessed datasets obtained from various sources.
- **processed/**: Houses datasets that have undergone cleaning and preprocessing, making them ready for analysis.
- **external/**: Includes data sourced from third parties or external organizations.
- **interim/**: Stores intermediate datasets generated during the data processing pipeline.
- **final/**: Contains the final datasets used for modeling and analysis.

### **scripts/**

- Contains scripts for data cleaning, transformation, and analysis to prepare the raw data for modeling and visualization.
