import pandas as pd
import os
import glob
import datetime
import geopandas as gpd
import warnings
warnings.filterwarnings("ignore")

variables_data_path = os.getcwd() + r'/Sources/master/'
print(variables_data_path)
HP_sd = gpd.read_file(os.getcwd()+ r'\Maps\hp_tehsil_final.geojson')
#HP_sd['object_id'] = HP_sd['object_id'].astype(int)

date_range = pd.date_range(start="2021-04-01", end="2024-12-31", freq='MS')

# Format the date values as "YYYY_MM" strings
formatted_dates = [date.strftime('%Y_%m') for date in date_range]

# Create a Pandas DataFrame with the values
dfs = []
for year_month in formatted_dates:
    df = HP_sd[['TEHSIL', 'object_id', 'dtcode11','tehsil_area','District']]
    df.columns = ['TEHSIL', 'object_id','dtcode11', 'tehsil_area','district']
    df['timeperiod'] = year_month
    dfs.append(df)
master_df = pd.concat(dfs).reset_index(drop = True)
#df = pd.DataFrame({'timeperiod': formatted_dates})
print(master_df)

# Variables for model input
monthly_variables = ['total_tender_awarded_value',
                     #'SOPD_tenders_awarded_value', 'SDRF_tenders_awarded_value', 'RIDF_tenders_awarded_value', 'LTIF_tenders_awarded_value', 'CIDF_tenders_awarded_value',
                      #'Preparedness Measures_tenders_awarded_value', 
                      'Immediate Measures_tenders_awarded_value', 
                      #'Others_tenders_awarded_value',
                      #'Total_Animal_Washed_Away', 'Total_Animal_Affected',
                      #'Population_affected_Total', 'Crop_Area',
                      #'Male_Camp', 'Female_Camp', 'Children_Camp',
                     #'Total_House_Fully_Damaged',
                     #'Human_Live_Lost_Children', 'Human_Live_Lost_Female', 'Human_Live_Lost_Male',
                     #'Embankments affected', 'Roads', 'Bridge', 'Embankment breached',
                     'rainfall','runoff',
                     #'ndvi_subdis', 'ndbi_subdis',
                     'inundation', #'riverlevel'
                     'structure_lost',
                     'health_centres_lost','health_amount',
                     'internalwatersupply','electricwires','Electricpoles','Roadlength','streetlights',
                     'person_dead','person_major_injury',
                     'schools_damaged','economic_loss',
                     'total_livestock_loss',
                     ]

for variable in monthly_variables:
    variable_df = pd.read_csv(variables_data_path + variable + '.csv')
    #print(variable_df)
    #variable_df['object_id'] = variable_df['object_id'].astype(int)
    #if variable in ['ndvi_subdis', 'ndbi_subdis']:
    #    continue#variable_df = variable_df.rename(columns = {'mean':'mean_'+variable[:4]})
    variable_df = variable_df.drop_duplicates()
    master_df = master_df.merge(variable_df, on=['object_id', 'timeperiod'], how='left')
'''
master_df['Relief_Camp_inmates'] = master_df['Male_Camp'].fillna(0).astype(int) \
    + master_df['Female_Camp'].fillna(0).astype(int) \
    + master_df['Children_Camp'].fillna(0).astype(int)
master_df['Human_Live_Lost'] = master_df['Human_Live_Lost_Children'].fillna(0).astype(int) \
    + master_df['Human_Live_Lost_Female'].fillna(0).astype(int) \
    + master_df['Human_Live_Lost_Male'].fillna(0).astype(int)


master_df = master_df.drop(['Male_Camp', 'Female_Camp', 'Children_Camp',
                            'Human_Live_Lost_Male', 'Human_Live_Lost_Children', 'Human_Live_Lost_Female'], axis=1)

'''
#Annual variables
master_df['year'] = master_df['timeperiod'].str[:4].astype(int)
annual_variables = ['mean_sex_ratio', 'sum_aged_population', 'sum_young_population', 'sum_population']#,
                    #'final_lu']

for variable in annual_variables:
    variable_df = pd.read_csv(variables_data_path + variable + '.csv')
    variable_df = variable_df.rename(columns = {'timeperiod': 'year'})
    master_df = master_df.merge(variable_df,
                                on = ['object_id', 'year'],
                                how='left')

zero_counts = master_df.apply(lambda x: (x == 0).sum())

print(zero_counts)
#print(master_df)

# one-time variables
onetime_variables = ['Schools', 'RailLengths', 'RoadLengths',#'HealthCenters','gcn250_average', 
                     'slope_elevation',
                      'antyodaya_variables', 'drainage_density','distance_from_river','rural_vul']
                     #'distance_from_river_polygon',]
master_df['year'] = ''

for variable in onetime_variables:
    print(variable)
    variable_df = pd.read_csv(variables_data_path + variable + '.csv')
    columns_to_drop = [col for col in ['timeperiod', 'District'] if col in variable_df.columns]
    if columns_to_drop:
        variable_df = variable_df.drop(columns=columns_to_drop)
    variable_df['year'] = ''
    print(f"master_df shape: {master_df.shape}")
    print(f"variable_df shape: {variable_df.shape}")
    master_df = master_df.merge(variable_df,
                                on = ['object_id','TEHSIL', 'year']
                                ,how='left')


master_df = master_df.drop([#'year', #'count_gcn250_pixels',
                            'count_bhuvan_pixels', 'count_inundated_pixels'], axis=1)

#master_df['year'] = master_df['timeperiod'].str[:4]
#master_df['month'] = master_df['timeperiod'].str[-2:]

#mean of sd
master_df['max_rain'] = master_df['max_rain'].fillna(master_df.groupby(['object_id'])['max_rain'].transform('mean'))
master_df['mean_rain'] = master_df['mean_rain'].fillna(master_df.groupby(['object_id'])['mean_rain'].transform('mean'))
master_df['sum_rain'] = master_df['sum_rain'].fillna(master_df.groupby(['object_id'])['sum_rain'].transform('mean'))

master_df['Sum_Runoff'] = master_df['Sum_Runoff'].fillna(master_df.groupby(['object_id'])['Sum_Runoff'].transform('mean'))
master_df['Peak_Runoff'] = master_df['Peak_Runoff'].fillna(master_df.groupby(['object_id'])['Peak_Runoff'].transform('mean'))
master_df['Mean_Daily_Runoff'] = master_df['Mean_Daily_Runoff'].fillna(master_df.groupby(['object_id'])['Mean_Daily_Runoff'].transform('mean'))


# Impute missing ANTYODAYA vars
master_df['block_nosanitation_hhds_pct'] = master_df['block_nosanitation_hhds_pct'].fillna(master_df.groupby(['district'])['block_nosanitation_hhds_pct'].transform('mean'))
master_df['block_piped_hhds_pct'] = master_df['block_piped_hhds_pct'].fillna(master_df.groupby(['district'])['block_piped_hhds_pct'].transform('mean'))
master_df['avg_tele'] = master_df['avg_tele'].fillna(master_df.groupby(['district'])['avg_tele'].transform('median')) #median
master_df['avg_electricity'] = master_df['avg_electricity'].fillna(master_df.groupby(['district'])['avg_electricity'].transform('mean'))
master_df['net_sown_area_in_hac'] = master_df['net_sown_area_in_hac'].fillna(master_df.groupby(['district'])['net_sown_area_in_hac'].transform('mean'))
'''
# Impute missing NDVI and NDBI
master_df = master_df.sort_values(by=['object_id', 'timeperiod'])
master_df['mean_ndvi'] = master_df['mean_ndvi'].ffill()
master_df['mean_ndbi'] = master_df['mean_ndbi'].ffill()
'''

# Impute all other vars with 0
master_df = master_df.fillna(0)
# Drop columns with suffixes "_x" and "_y"
master_df = master_df.loc[:, ~master_df.columns.str.endswith('_x') & ~master_df.columns.str.endswith('_y')]

master_df.to_csv(os.getcwd() + r'/Sources/MASTER_VARIABLES.csv', index=False)
#master_df[master_df.duplicated(subset= ['object_id', 'timeperiod'])].to_csv('MASTER_VARIABLES.csv', index=False)

print(master_df.shape)