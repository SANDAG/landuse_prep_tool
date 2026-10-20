# %%
import numpy as np
import os
import pandas as pd
import geopandas as gpd
import sys
import yaml
import random
from sqlalchemy import create_engine

lu_lib = os.path.dirname(os.path.dirname(__file__))
lu_lib = os.path.join(lu_lib, "1_1_Parking/3_costs_estimation")
sys.path.insert(1, lu_lib)
import estimate_parking_costs as park_func

# %%
#Reading properties from config file
if len(sys.argv) < 2:
    print("Config input missing - Usage: python run_preprocess.py arg1")
    sys.exit(1)

config_file = sys.argv[1]

with open(config_file) as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

input_dir = cfg['input_dir']
parking_output = cfg['parking_output_dir']
scenario_year = cfg['scenario_year']
write_dir = cfg['output_dir']
EF_dir = cfg['EF_dir']
ff_effective_year = cfg.get('ff_year', scenario_year)

#Reading from SQL SERVER
server = cfg['server']
database = cfg['database']
connection_string = f'mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes'
engine = create_engine(connection_string)

xref_df = pd.read_sql('SELECT * FROM sde.MGRA15_RP2025_ABM3_XREF', engine)
xref_df = xref_df.rename(columns={'MGRA':'mgra'})
# print(xref_df.columns)

# %%
landuse_file = os.path.join(EF_dir,cfg['landuse_file'].replace('${scenario_year}', str(scenario_year)))

micro_mobility_file = os.path.join(input_dir,cfg['micro_mob_file'])

auxiliary_file = os.path.join(input_dir,cfg['auxiliary_file']) #2019 school, remoteAVParking	refueling_stations


imputed_parking_df = pd.read_csv(os.path.join(parking_output,cfg["imputed_parking_df"])).set_index('mgra')
if cfg.get('landuse_from_databricks', False):
    from read_databricks import read_run
    print(f"Reading land use for PopulationSim run {cfg['popsim_run_id']} from Databricks")
    landuse_df = read_run(cfg['popsim_run_id'], table=cfg['popsim_landuse_table'])
    run_years = landuse_df['year'].unique()
    if list(run_years) != [scenario_year]:
        raise ValueError(f"PopulationSim run {cfg['popsim_run_id']} is for year(s) {list(run_years)}, "
                         f"but scenario_year is {scenario_year}")
    # Match the E&F CSV: drop the run metadata columns and use int64 like read_csv
    landuse_df = landuse_df.drop(columns=['run_id', 'run_timestamp', 'year'])
    int_cols = landuse_df.select_dtypes('integer').columns
    landuse_df[int_cols] = landuse_df[int_cols].astype('int64')
else:
    landuse_df = pd.read_csv(landuse_file)
lu_df = landuse_df.set_index("mgra")
print("Reading MGRA shapefile data")
mgra_gdf = gpd.read_file(cfg["geometry_file"]).set_index("MGRA")[ #mgra index removed
    ["TAZ", "geometry"]
]
street_data = pd.read_csv(os.path.join(parking_output,cfg["street_file"])).set_index("MGRA")
model_params_free = pd.read_csv(os.path.join(parking_output,cfg["model_params_free"]))
model_params_paid = pd.read_csv(os.path.join(parking_output,cfg["model_params_paid"]))
max_dist = cfg["walk_dist"]
walk_coef = cfg["walk_coef"]

#Parking Policy
policy_flag = cfg['implement_policy']
policy_type = ''
if policy_flag:
    policy_type = cfg['policy_type']
    print(f"Applying parking policy to {policy_type} MGRAs")
    parking_policy = os.path.join(parking_output,cfg['parking_policy'].replace('${scenario_year}', str(scenario_year)))
    rate = cfg['update_rate']
    #Finding index to update Mohubs Parking policy
    valid_hourly_costs_idx = imputed_parking_df[imputed_parking_df['hourly_imputed'].notnull() & (imputed_parking_df['hourly_imputed'] > 0)].index
    # imputed_parking_df.to_csv('imputed_parking_df1.csv')
#########################################################################
#Parking File Creation
def parking_costs()-> pd.DataFrame:
    acres = (mgra_gdf.geometry.area / 43560).to_frame("acres")
    full_streetdata_df = street_data[["length", "intcount"]].join(acres).join(lu_df[["hh_sf", "hh_mf", "emp_total","emp_ret","emp_food","emp_hlth"]])
    
    global imputed_parking_df
    global valid_hourly_costs_idx

    #Fullstreet data used to estimate paid and free spaces
    ############################################
    #Estimate paid spaces
    full_streetdata_df['est_paid_spaces'] = park_func.estimate_spaces_df(full_streetdata_df[["length", "intcount", "acres", "hh_sf", "emp_total"]],model_params_paid)
    if policy_type=='mohubs' and policy_flag:
        #Limit the estimated paid spaces with max_est_paid_spaces in config
        full_streetdata_df.loc[full_streetdata_df.est_paid_spaces>cfg['max_est_paid_spaces'],'est_paid_spaces']=cfg['max_est_paid_spaces']

        #Estimate free spaces
        full_streetdata_df['est_free_spaces'] = park_func.estimate_spaces_df(full_streetdata_df[["length", "intcount", "hh_sf", "hh_mf", "emp_total"]],model_params_free)
        #Limit the estimated free spaces with max_est_free_spaces in config
        full_streetdata_df.loc[full_streetdata_df.est_free_spaces>cfg['max_est_free_spaces'],'est_free_spaces']=cfg['max_est_free_spaces']

        #replacing empty paid spaces in imputed df with estimated values where costs are available
        imputed_parking_df.loc[(imputed_parking_df.hourly_imputed>0) & ((imputed_parking_df.paid_spaces<=0) | (pd.isnull(imputed_parking_df['paid_spaces']))),'paid_spaces']=full_streetdata_df['est_paid_spaces']
    
        #replacing empty free spaces with estimated values
        imputed_parking_df.loc[(imputed_parking_df.free_spaces<=0) | (pd.isnull(imputed_parking_df['free_spaces'])),'free_spaces']=full_streetdata_df['est_free_spaces']

        #Keeping only MGRA with Employment in Health, Retail and food
        full_streetdata_df['emp_ret_food_hlth'] = full_streetdata_df['emp_ret'] + full_streetdata_df['emp_food'] + full_streetdata_df['emp_hlth']
        emp_idx = full_streetdata_df[full_streetdata_df['emp_ret_food_hlth']>=30].index
        valid_indices = [index for index in emp_idx if index in imputed_parking_df.index]

        #Union of indices from employee and inventory hourly costs
        union_indices = set(valid_indices).union(set(valid_hourly_costs_idx))
        # imputed_parking_df.to_csv('imputed_parking_df2.csv')
        # Filter imputed_parking_df using the union of indices
        imputed_parking_df = imputed_parking_df.loc[list(union_indices)]
        
        #Creating Districts with updated imputed_parking_df
        districts_df = park_func.create_districts(imputed_parking_df,mgra_gdf,max_dist)
    #####################################
    else:
        #replacing empty paid spaces in imputed df with estimated values where costs are available
        condition = (imputed_parking_df.hourly_imputed>0) & ((imputed_parking_df.paid_spaces<=0) | (pd.isnull(imputed_parking_df['paid_spaces'])))
        full_streetdata_df.rename_axis("mgra", inplace=True)
        aligned_est_paid_spaces = full_streetdata_df.reindex(imputed_parking_df.index)
        imputed_parking_df.loc[condition,'paid_spaces']=aligned_est_paid_spaces['est_paid_spaces']
        
        #Creating Districts with updated imputed_parking_df
        districts_df = park_func.create_districts(imputed_parking_df,mgra_gdf,max_dist)
        full_streetdata_df['est_free_spaces'] = park_func.estimate_spaces_df(full_streetdata_df[["length", "intcount", "hh_sf", "hh_mf", "emp_total"]],model_params_free)    
        # districts_df.to_csv(os.path.join('./districts.csv'))
    
    #####################################

    cost_df = districts_df.loc[districts_df.is_prkdistrict]
    cost_df = cost_df.join(full_streetdata_df[["est_paid_spaces","est_free_spaces"]],how='left')
    imputed_names = {k + "_imputed": k for k in ["hourly", "daily", "monthly"]}
    imputed_parking_df = imputed_parking_df.drop(columns=["hourly", "daily", "monthly"])
    imputed_parking_df = imputed_parking_df.rename(columns=imputed_names)

    cost_df = cost_df.join(imputed_parking_df[["hourly", "daily", "monthly",'paid_spaces','free_spaces']])
    # cost_df.to_csv('./cost_df.csv')

    #Updating spaces wrt parking type and existing spaces
    cost_df[['paid_spaces','free_spaces']]=cost_df[['paid_spaces','free_spaces']].fillna(0)
    cost_df['cost_spaces']=0
    cost_df = cost_df[~cost_df.index.duplicated()]

    cost_df.loc[(cost_df['parking_type']==1) & (cost_df['paid_spaces']>0),'cost_spaces'] = cost_df["paid_spaces"]
    cost_df.loc[(cost_df['parking_type']==1) & (cost_df['paid_spaces']<=0),'cost_spaces'] = cost_df["est_paid_spaces"]
    cost_df.loc[(cost_df['parking_type']==2) & (cost_df['free_spaces']>0),'cost_spaces'] = cost_df["free_spaces"]
    cost_df.loc[(cost_df['parking_type']==2) & (cost_df['free_spaces']<=0),'cost_spaces'] = cost_df["est_free_spaces"]

    noprk_zones = districts_df.loc[
        districts_df.is_prkdistrict & districts_df.is_noprkspace
    ]
    cost_df.loc[noprk_zones.index, "cost_spaces"] = 0

    exp_prkcosts_df = park_func.run_expected_parking_cost(max_dist,walk_coef,districts_df,mgra_gdf,cost_df)
    
    #Updating spaces wrt parking type and existing spaces with estimated free spaces
    cost_df.loc[(cost_df['parking_type']==2) & (cost_df['free_spaces']<=0),'free_spaces'] = cost_df["est_free_spaces"]
    cost_df['total_spaces'] = cost_df[["paid_spaces", "free_spaces"]].sum(axis=1)

    parking_df = exp_prkcosts_df.join(districts_df['parking_type']).join(cost_df['total_spaces'])
    parking_df['total_spaces'].fillna(0,inplace=True)
    parking_df.rename(columns={'total_spaces':'parking_spaces'},inplace=True)
    parking_df.index = parking_df.index.set_names('mgra')
    
    # parking_df.to_csv(f"./final_parking_df_{policy_flag}_{scenario_year}.csv")
    return parking_df

def process_parking_policy()-> pd.DataFrame:
    df_policy = pd.read_csv(parking_policy)
    global xref_df
    mgra_parking_rates = pd.merge(xref_df,df_policy,on='MoHubType',how='left')

    if policy_type == 'pca':
        mgra_parking_rates.loc[mgra_parking_rates['PCAID'].isnull(),['Hourly','Daily','Monthly']] = None

    mgra_parking_rates = mgra_parking_rates[['mgra','Hourly','Daily','Monthly']]
    mgra_parking_rates.dropna(subset=['Hourly'],inplace=True) #Removing all mgra where we don't provide a new parking rate
    imputed_parking_df.reset_index(inplace=True)
  
    #Outer join to keep all MGRA not in inventory file
    merged_df = pd.merge(imputed_parking_df,mgra_parking_rates,on='mgra',how='outer')

    merged_df['Hourly'] = merged_df['Hourly']*rate
    merged_df['Daily'] = merged_df['Daily']*rate
    merged_df['Monthly'] = merged_df['Monthly']*rate

    #Maintaining original imputed values if policy rates are NULL or less than original
    merged_df['hourly_imputed'] = np.where((merged_df['Hourly'].isna()) | (merged_df['Hourly']<merged_df['hourly_imputed']),merged_df['hourly_imputed'],merged_df['Hourly'])
    merged_df['daily_imputed'] = np.where((merged_df['Daily'].isna()) | (merged_df['Daily']<merged_df['daily_imputed']),merged_df['daily_imputed'],merged_df['Daily'])
    merged_df['monthly_imputed'] = np.where((merged_df['Monthly'].isna()) | (merged_df['Monthly']<merged_df['monthly_imputed']),merged_df['monthly_imputed'],merged_df['Monthly'])
    # merged_df.to_csv('./merged_df_pca_policy.csv', index=False)
    # sys.exit(1)
    # merged_df.to_csv(os.path.join(write_dir, 'merged_df_policy.csv'), index=True)
    merged_df.drop(columns=['Hourly','Daily','Monthly'],inplace=True)
    merged_df.set_index('mgra', inplace=True)
    merged_df.sort_index(ascending=True, inplace=True)

    return merged_df


if policy_flag:
    imputed_parking_df = process_parking_policy()
    # print(imputed_parking_df[['hourly_imputed','daily_imputed','monthly_imputed']])

parking_df = parking_costs()
print("Parking df created")

#########################################################################
# %%
def process_landuse()-> pd.DataFrame:
    '''
        Series15 land use (ABM3) does not contain all of the same columns as ABM2+ land use.
        This function will tranform the Series 15 to match what is expected.
        
        If these column names are changed, then the corresponding names need to be changed in the configs.
    '''
    print('Working on Landuse file')
    df_mgra = landuse_df.copy()
    mmfile = pd.read_csv(micro_mobility_file)
    df_auxiliary = pd.read_csv(auxiliary_file)


    #Mapping mobility hubs to mgra
    mmfile = mmfile[['MoHubType','Access_Time']].set_index('MoHubType')
    xref_df['MicroAccessTime'] = xref_df['MoHubType'].map(mmfile['Access_Time'])
    landuse_rename_dict = {
        'zip': 'zip09',
        'majorcollegeenroll_total': 'collegeenroll',
        'othercollegeenroll_total': 'othercollegeenroll',
        'acre': 'acres',
        'landacre':'land_acres',
        'LUZ':'luz_id',
        'emp_tot': 'emp_total'}
    df_mgra = df_mgra.rename(columns=landuse_rename_dict)

    merged_df = pd.merge(df_mgra, parking_df, on='mgra', how='left')
    merged_df = pd.merge(merged_df, df_auxiliary, on='mgra', how='left') #School df can be added
    merged_df = pd.merge(merged_df,xref_df[['mgra','MicroAccessTime','MoHubName']],on='mgra',how='left')
    # merged_df = merged_df.drop('MGRA', axis=1)
    merged_df[['MicroAccessTime','MoHubName']] = merged_df[['MicroAccessTime','MoHubName']].fillna(999)
    merged_df['MicroAccessTime']= merged_df['MicroAccessTime'].astype(int)

    #Set Micro Access Time to 999 if not in SD for years before 2035
    Mohubs_SD = ['West Bernardo', 'College Area', 'Southeast San Diego', 'La Jolla', 'University Community', 'Kearny Mesa', 'Sorrento Valley', 'Mira Mesa', 'US-Mexico Border', 'Ocean Beach', 'Pacific Beach', 'Carmel Valley', 'Urban Core', 'Mission Valley', 'Linda Vista/Serra Mesa', 'Encanto']
    if scenario_year < 2035:
        merged_df.loc[~merged_df['MoHubName'].isin(Mohubs_SD), 'MicroAccessTime'] = 999

    #NEW XREF Code
    xref_df['microtransit'] = xref_df['MTID'].str.extract('(\d+)').fillna(0).astype(int)
    xref_df['nev'] = xref_df['NEVID'].str.extract('(\d+)').fillna(0).astype(int)

    #Checking phase years for MT implementation
    phased_mm_df = xref_df[
        (xref_df['MTYear'] <= ff_effective_year)
    ]
    phased_nev_df =  xref_df[
        (xref_df['NEVYear'] <= ff_effective_year)
    ]

    #Adding condition for No Build case - MT = Not available and NEV = Downtown and Oceanside
    if ff_effective_year < 2025 :
        phased_mm_df = pd.DataFrame({
            "microtransit": [0] * 5
        })
        phased_mm_df['mgra'] = [i % 5 + 1 for i in range(5)]
        phased_nev_df =  xref_df[
            (xref_df['NEVID'] == 'FF14') | (xref_df['NEVID'] == 'FF10')
        ]

    merged_df = pd.merge(merged_df, phased_mm_df[['mgra','microtransit']], on='mgra', how='left')
    merged_df = pd.merge(merged_df, phased_nev_df[['mgra','nev']], on='mgra', how='left')
    merged_df[['microtransit','nev']] = merged_df[['microtransit','nev']].fillna(0)

    #Duplicate check
    dup_count = merged_df.duplicated(subset=['mgra']).sum()
    assert dup_count == 0, f"Duplicate records found: {dup_count}"

    #Dropping MoHubName as it is string field, not int
    merged_df = merged_df.drop(columns=['MoHubName'], axis=1)
    return merged_df.sort_values(by='mgra')

# %%
process_landuse().to_csv(os.path.join(write_dir, f'mgra15_based_input{scenario_year}.csv'), index=False)
