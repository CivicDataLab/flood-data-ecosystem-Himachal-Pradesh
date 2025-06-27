import pandas as pd
import os
import geopandas as gpd

data_path = os.getcwd()+r'\Sources\TENDERS\data'
HP_sd_gdf = gpd.read_file(os.getcwd()+r'\Maps\hp_tehsil_final.geojson')

flood_tenders_geotagged_df = pd.read_csv(data_path + r'\floodtenders_Tehsil-geotagged.csv')
flood_tenders_geotagged_df['tender_subdistrict'] = flood_tenders_geotagged_df['tender_subdistrict'].str.upper()
flood_tenders_geotagged_df['DISTRICT_FINALISED'] = flood_tenders_geotagged_df['DISTRICT_FINALISED'].str.upper()
#flood_tenders_geotagged_df = flood_tenders_geotagged_df.drop('District',axis=1)
flood_tenders_geotagged_df = flood_tenders_geotagged_df.merge(HP_sd_gdf,
                                 left_on = ['DISTRICT_FINALISED', 'tender_subdistrict'],
                                 right_on = ['District', 'TEHSIL'],
                                 how='left')
#flood_tenders_geotagged_df.to_csv(r"D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\HP\flood-data-ecosystem-Himachal-Pradesh\Sources\TENDERS\scripts\test.csv")

#flood_tenders_geotagged_df.rename(columns={'Awarded Price in ₹':'Awarded Value'},inplace = True)
flood_tenders_geotagged_df = flood_tenders_geotagged_df.dropna(subset=['Awarded Value'])# = flood_tenders_geotagged_df['Awarded Value'].fillna(flood_tenders_geotagged_df['Awarded Price in ₹'])
#print(flood_tenders_geotagged_df['Awarded Value'].head())
#print(type(flood_tenders_geotagged_df['Awarded Value']))

flood_tenders_geotagged_df['Awarded Value'] = (
    flood_tenders_geotagged_df['Awarded Value'].astype(str)  # Convert all values to strings
    .str.replace(',', '', regex=False)  # Remove commas
    #.replace(' ', '0')  # Replace string 'nan' with '0'
    .astype(float)  # Convert to float
)
print(flood_tenders_geotagged_df)
# Total tender variable
variable = 'total_tender_awarded_value'
total_tender_awarded_value_df = flood_tenders_geotagged_df.groupby(['month', 'object_id'])[['Awarded Value']].sum().reset_index()
total_tender_awarded_value_df = total_tender_awarded_value_df.rename(columns = {'Awarded Value': variable})
print(total_tender_awarded_value_df)


for year_month in total_tender_awarded_value_df.month.unique():
    variable_df_monthly = total_tender_awarded_value_df[total_tender_awarded_value_df.month == year_month]
    variable_df_monthly = variable_df_monthly[['object_id', variable]]
    #print(variable_df_monthly)
    if os.path.exists(data_path+'/variables/'+variable):
        variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
    else:
        os.mkdir(data_path+'/variables/'+variable)
        variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)



# Scheme wise tender variables
variables = flood_tenders_geotagged_df['Scheme'].unique()
for variable in variables:
    variable_df = flood_tenders_geotagged_df[flood_tenders_geotagged_df['Scheme'] == variable]
    variable_df= variable_df.groupby(['month', 'object_id'])[['Awarded Value']].sum().reset_index()
    
    variable = str(variable) + '_tenders_awarded_value'
    variable_df = variable_df.rename(columns = {'Awarded Value': variable})
    
    for year_month in variable_df.month.unique():
        variable_df_monthly = variable_df[variable_df.month == year_month]
        variable_df_monthly = variable_df_monthly[['object_id', variable]]
        if os.path.exists(data_path+'/variables/'+variable):
            variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
        else:
            os.mkdir(data_path+'/variables/'+variable)
            variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)


# Scheme wise tender variables
variables = flood_tenders_geotagged_df['Response Type'].unique()
for variable in variables:
    variable_df = flood_tenders_geotagged_df[flood_tenders_geotagged_df['Response Type'] == variable]
    variable_df= variable_df.groupby(['month', 'object_id'])[['Awarded Value']].sum().reset_index()

    variable = str(variable) + '_tenders_awarded_value'
    variable_df = variable_df.rename(columns = {'Awarded Value': variable})

    for year_month in variable_df.month.unique():
        variable_df_monthly = variable_df[variable_df.month == year_month]
        variable_df_monthly = variable_df_monthly[['object_id', variable]]
        if os.path.exists(data_path+'/variables/'+variable):
            variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
        else:
            os.mkdir(data_path+'/variables/'+variable)
            variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)

    '''
    for year_month in variable_df.month.unique():
        variable_df_monthly = variable_df[variable_df.month == year_month]
        variable_df_monthly = variable_df_monthly[['object_id', variable]]
        if os.path.exists(data_path+'variables/'+variable):
            variable_df_monthly.to_csv(data_path+'variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
        else:
            os.mkdir(data_path+'variables/'+variable)
            variable_df_monthly.to_csv(data_path+'variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
'''