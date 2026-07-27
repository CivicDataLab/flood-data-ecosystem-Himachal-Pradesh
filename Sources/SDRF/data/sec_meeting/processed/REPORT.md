# Assam SEC / SDRF minutes — analysis

## 0. Corpus & data coverage

- Documents parsed: **14**
- Meeting date range: **2019–2023**
- Meetings with a parseable date: **13/14**
- Allocation line-items extracted: **834**
- Summary/total/header rows excluded from sums: **16** (see `row_kind` in `line_items.csv`)
- Line-items above the per-item ceiling flagged for review: **3** (`amount_outlier=True`)
- Total allocation captured: **₹3406.347 crore**
- Line-items with low-confidence auto-classification: **25%** (review these before quoting work-type/phase splits)

## 1. Spending patterns over time

|   year |   allocation_cr |   meetings_with_data |
|-------:|----------------:|---------------------:|
|   2019 |         567.34  |                    2 |
|   2020 |         201.903 |                    2 |
|   2022 |         469.418 |                    2 |
|   2023 |        1800.63  |                    7 |

> Caveat: yearly totals reflect *which meetings approved money*, not a steady budget series — SDRF approval meetings are irregular and some years have none. Treat gaps as missing data, not zero spend.

## 2. District & department analysis (allocation)

**Top districts (₹ crore):**

| district   |   allocation_cr |
|:-----------|----------------:|
| Kangra     |         217.573 |
| Kullu      |         213.703 |
| Una        |         211.767 |
| Shimla     |         179.712 |
| Mandi      |         173.855 |
| Chamba     |         169.885 |
| Hamirpur   |         146.037 |
| Solan      |          88.818 |
| Kinnaur    |          68.126 |
| Bilaspur   |          63.956 |

**By department (₹ crore):**

| department                     |   allocation_cr |
|:-------------------------------|----------------:|
| Revenue & DM                   |        2882.12  |
| PWD                            |         326.127 |
| Disaster Response Force        |          49.605 |
| Disaster Management Cell       |          49.534 |
| State Disaster Mitigation Fund |          48.757 |
| Jal Shakti                     |          42     |
| Disaster Management            |           5.2   |
| Director Horticulture          |           2     |
| Agriculture                    |           1     |

> Utilisation vs allocation: the minutes record *approved allocations*. Actual fund **utilisation/expenditure** appears only sporadically inside Action-Taken-Reports and is not a structured column — so a clean allocation-vs-utilisation comparison is **not** reliably available from this corpus. Allocation is reported here; utilisation is partial at best.

## 3. Types of work

| work_type                          |   items |   allocation_cr |
|:-----------------------------------|--------:|----------------:|
| Roads & Bridges                    |     136 |         855.521 |
| Relief / Gratuitous assistance     |     249 |         666.105 |
| Other / Unclassified               |     215 |         537.55  |
| Water supply / Sanitation          |      44 |         407.519 |
| Restoration of damaged assets      |      74 |         379.893 |
| Embankment / Flood protection      |      35 |         243.709 |
| Drainage / De-silting              |      31 |         189.82  |
| Buildings / Shelter                |      10 |          81.05  |
| Equipment / Procurement            |      14 |          20.546 |
| Health / Veterinary response       |      21 |          18.3   |
| Schools / Education infrastructure |       3 |           6.275 |
| Capacity building / Training       |       2 |           0.058 |

_(work-type × department cross-tab saved to `03_worktype_by_department.csv`)_

## 4. Stakeholder / attendance analysis

- Distinct attendees identified: **35** across **12** meetings

**Most frequent attendees:**

| name                                                                      |   meetings |
|:--------------------------------------------------------------------------|-----------:|
| Onkar Chand Sharma                                                        |         22 |
| Sudesh Kumar Mokhta                                                       |         13 |
| D.C. Rana                                                                 |         13 |
| R.D. Dhiman                                                               |          3 |
| The Special Secretary (Finance)                                           |          2 |
| The Deputy Commissioner                                                   |          2 |
| Guard file                                                                |          2 |
| Balwan Chand                                                              |          2 |
| The Section Officer (Finance exp.)                                        |          1 |
| The Section Officer (Finance Expenditure), H.P. Sectt. Shimla-2           |          1 |
| The Deputy Commissioner-cum-Chairman, DDMAs, concerned district(s) in HP. |          1 |
| The Section Officer (Finance Expenditure)                                 |          1 |
| The Principal Secretary (Finance) to the Govt. of H.P.                    |          1 |
| The Treasury Officer                                                      |          1 |
| The Engineer-in-Chief (HPPWD), Nirman Bhawan, Shimla-2                    |          1 |

**Departments represented (by attendance count):**

| department                     |   appearances |
|:-------------------------------|--------------:|
| Government of Himachal Pradesh |            32 |
| Revenue & DM                   |            25 |
| Govt. of HP                    |             2 |
| HP Sectt.                      |             1 |
| Himachal Pradesh               |             1 |
| Mandi                          |             1 |
| Rev-DM                         |             1 |
| Shimla Division                |             1 |
| Solan                          |             1 |
| State Executive Committee      |             1 |

## 5. Disaster-management phase split

| disaster_phase         |   items |   allocation_cr |
|:-----------------------|--------:|----------------:|
| Long-term Preparedness |      24 |         100.238 |
| Mitigation             |      56 |         392.288 |
| Repair and Restoration |     440 |        2042.09  |
| Unclassified           |     314 |         871.735 |

> Phase labels are inferred from work descriptions with a keyword rubric (preparedness / mitigation / response-repair-restoration). Many SDRF items are 'Immediate Measures' which are inherently response/restoration; genuinely preventive 'mitigation' spend is the harder, more ambiguous bucket — verify low-confidence rows.

## 5b. Disaster type (notified hazards)

| disaster_type              |   items |   allocation_cr |
|:---------------------------|--------:|----------------:|
| Unspecified / Multi-hazard |     776 |        3075.15  |
| Flood                      |      31 |         225.407 |
| Storm / Wind (Bordoisila)  |       2 |          44.96  |
| Erosion (river/bank)       |       5 |          25.055 |
| Landslide                  |      11 |          24.839 |
| Fire                       |       6 |           9.134 |
| Earthquake                 |       2 |           1.416 |
| Cloudburst                 |       1 |           0.386 |

> Disaster type is inferred from each row's text against the SDRF/NDRF notified-disaster list plus Assam's locally-notified hazards (storm/Bordoisila, river erosion, lightning). Rows whose text names no hazard (e.g. a bare school name) fall in 'Unspecified / Multi-hazard'; the hazard there sits in the table header/narrative, not the row.

## 6. How priorities shifted over time

_Phase share by year saved to `06_phase_share_by_year.csv` and `charts/06_phase_share.png`._
_Work-type share by year saved to `06_worktype_share_by_year.csv`._
