import pandas as pd
import pandas as pd
import os
import geopandas as gpd
import dateutil

data_path = os.getcwd()+r'Sources\HPSDMA\data\SDRF\relief_and_mitigation_funds_final.csv'
assam_rc_gdf = gpd.read_file(os.getcwd()+r'\IDS-DRR-Assam\Maps\as_ids-drr_shapefiles\assam_rc_2024-11.geojson')

flood_expenditure_geotagged_df = pd.read_csv(data_path + r'flood_expenses_RCgeotagged.csv')
flood_expenditure_geotagged_df = flood_expenditure_geotagged_df.merge(assam_rc_gdf,
                                 left_on = ['DISTRICT_FINALISED', 'REVENUE_CIRCLE_FINALISED'],
                                 right_on = ['dtname', 'revenue_ci'],
                                 how='left')
flood_expenditure_geotagged_df['Total Approval Amount'] = flood_expenditure_geotagged_df['Total Administrative Approval Amount In Lakhs'] * 100000

for index, row in flood_expenditure_geotagged_df.iterrows():
        proposal_date = dateutil.parser.parse(row['Proposal Date'])
        month = row['Proposal Date'][3:5]
        year = str(proposal_date.year)
        timeperiod = year + '_'+ month
        flood_expenditure_geotagged_df.loc[index, "timeperiod"] = timeperiod

# Total tender variable
variable = 'total_expenditure_value'
total_expenditure_value_df = flood_expenditure_geotagged_df.groupby(['timeperiod', 'object_id'])[['Total Approval Amount']].sum().reset_index()
total_expenditure_value_df = total_expenditure_value_df.rename(columns = {'Total Approval Amount': variable})
#print(total_expenditure_value_df)

for year_month in total_expenditure_value_df.timeperiod.unique():
    variable_df_monthly = total_expenditure_value_df[total_expenditure_value_df.timeperiod == year_month]
    variable_df_monthly = variable_df_monthly[['object_id', variable]]
    print(data_path)
    if os.path.exists(data_path+'variables/'+variable):
        variable_df_monthly.to_csv(data_path+'variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
    else:
        os.mkdir(data_path+'variables/'+variable)
        variable_df_monthly.to_csv(data_path+'/variables/'+variable+'/{}_{}.csv'.format(variable, year_month), index=False)
