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
households_file = os.path.join(EF_dir,cfg['households_file'].replace('${scenario_year}', str(scenario_year)))
persons_file = os.path.join(EF_dir,cfg['persons_file'].replace('${scenario_year}', str(scenario_year)))
landuse_file = os.path.join(EF_dir,cfg['landuse_file'].replace('${scenario_year}', str(scenario_year)))

micro_mobility_file = os.path.join(input_dir,cfg['micro_mob_file'])

auxiliary_file = os.path.join(input_dir,cfg['auxiliary_file']) #2019 school, remoteAVParking	refueling_stations


imputed_parking_df = pd.read_csv(os.path.join(parking_output,cfg["imputed_parking_df"])).set_index('mgra')
lu_df = pd.read_csv(landuse_file).set_index("mgra")
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
def process_household()-> pd.DataFrame:
    '''
        Series15 synthetic population (ABM3) does not contain all of the same columns as ABM2+ syn pop.
        This function will tranform the Series 15 to match what is expected.
        
        If these column names are changed, then the corresponding names need to be changed in the configs.
    '''
    households = pd.read_csv(households_file)
    xref_taz_mgra = pd.read_csv(landuse_file)[['mgra','taz']]
    households_rename_dict = {
        'household_id': 'hhid',
        'HHADJINC': 'hinc',
        'VEH': 'veh',
        'NP': 'persons',
        'HHT': 'hht',
        'BLD': 'bldgsz'}
    
    #get taz of household location
    households = households.merge(xref_taz_mgra, on='mgra')
    households = households.rename(columns=households_rename_dict)
    
    #create household serial number; version
    households['household_serial_no'] = 0
    households['version'] = 0
    
    #create poverty (ref: ASPE 2022 Poverty guidelines)
    households['poverty_guideline'] = 13590
    households.loc[(households['persons'] == 2), 'poverty_guideline'] = 18310
    households.loc[(households['persons'] == 3), 'poverty_guideline'] = 23030
    households.loc[(households['persons'] == 4), 'poverty_guideline'] = 27750
    households.loc[(households['persons'] == 5), 'poverty_guideline'] = 32470
    households.loc[(households['persons'] == 6), 'poverty_guideline'] = 37190
    households.loc[(households['persons'] == 7), 'poverty_guideline'] = 41910
    households.loc[(households['persons'] == 8), 'poverty_guideline'] = 46630
    households.loc[(households['persons'] >= 9), 'poverty_guideline'] = 46630 + 4720* (households['persons']-8)
    
    households['poverty'] = households['hinc']/households['poverty_guideline']
    
    households['hinc'].fillna(0,inplace=True) #newly added

    #create household income category
    conditions = [(households["hinc"] < 30000),
                  ((households["hinc"] >= 30000) & (households["hinc"] < 60000)),
                  ((households["hinc"] >= 60000) & (households["hinc"] < 100000)),
                  ((households["hinc"] >= 100000) & (households["hinc"] < 150000)),
                  (households["hinc"] >= 150000)]
    choices = [1,2,3,4,5]
    households["hinccat1"] = pd.Series(np.select(conditions, choices, default=1), dtype="int")
    
    #create number of workers in household
    # households['num_workers'] = households['WIF']
    # households.loc[(households['WIF']==3) & (households['persons']>=3) & (households['HUPAC']>=4), 'num_workers'] = households['persons']
    households['num_workers'] = households['workers']
    households.loc[(households['workers']==3) & (households['persons']>=3) & (households['HUPAC']>=4), 'num_workers'] = households['persons']

    #fill NaN with o
    households['num_workers'].fillna(0, inplace=True)
    households['veh'].fillna(0, inplace=True)
    
    #create household unit type
    # households['unittype'] = households['GQ_type']
    # households.loc[(households['GQ_type'].isin([1,2,3])), 'unittype'] = 1
    households['unittype'] = households['gq_type']
    households.loc[(households['gq_type'].isin([1,2,3])), 'unittype'] = 1
    
    #integer type of fields
    households['unittype']= households['unittype'].astype(int)
    households['hht']= households['hht'].astype(int)
    households['bldgsz']= households['bldgsz'].astype(int)
    households['num_workers']= households['num_workers'].astype(int)
    households['veh']= households['veh'].astype(int)
    # households['hinc']= households['hinc'].astype(int)
    
    return households[["hhid",
                       "household_serial_no",
                       "taz",
                       "mgra", #mgra
                       "hinccat1",
                       "hinc",
                       "num_workers",
                       "veh",
                       "persons",
                       "hht",
                       "bldgsz",
                       "unittype",
                       "version",
                       "poverty"]].sort_values(by=['hhid'])

# %%
def process_persons()-> pd.DataFrame:
    '''
        Series15 synthetic population (ABM3) does not contain all of the same columns as ABM2+ syn pop.
        This function will tranform the Series 15 to match what is expected.
        
        If these column names are changed, then the corresponding names need to be changed in the configs.
    '''
    persons = pd.read_csv(persons_file)
    persons_rename_dict = {
        'household_id': 'hhid',
        'SPORDER': 'pnum',
        'AGEP': 'age',
        'SEX': 'sex',
        'RAC1P': 'rac1p',
        'WKW': 'weeks',
        'WKHP': 'hours',
        'SOC2': 'soc2'}
    
    persons['naics2_original_code'] = persons['NAICS2']
    persons['naics2_original_code']=persons['naics2_original_code'].fillna(0)
    persons = persons.rename(columns=persons_rename_dict).sort_values(by=['hhid','pnum'])
    
    #create household serial number; perid
    persons['household_serial_no'] = 0
    persons['version'] = 0
    persons['perid'] = range(1, 1+len(persons))
    
    PEMPLOY_FULL, PEMPLOY_PART, PEMPLOY_NOT, PEMPLOY_CHILD = 1, 2, 3, 4
    persons['pemploy'] = np.zeros(len(persons))
    persons['pemploy'] = np.where(persons.age < 16, PEMPLOY_CHILD, PEMPLOY_PART)
    persons['pemploy'] = np.where((persons.age >= 16) & ((persons.ESR == 3) | (persons.ESR == 6)), PEMPLOY_NOT, persons['pemploy'])
    persons['pemploy'] = np.where((persons.age>=16) & ((persons.ESR != 3) & (persons.ESR != 6)) & (persons.hours >= 35), PEMPLOY_FULL, persons['pemploy'])
    persons['pemploy'] = persons['pemploy'].astype(int)

    PSTUDENT_GRADE_OR_HIGH, PSTUDENT_UNIVERSITY, PSTUDENT_NOT = 1, 2, 3
    persons['pstudent'] = np.zeros(len(persons))
    persons['pstudent'] = np.where((persons.pemploy == 1) & (persons.age >= 16), PSTUDENT_NOT, persons.pstudent)
    persons['pstudent'] = np.where((persons.pemploy == 1) & (persons.age < 16), PSTUDENT_GRADE_OR_HIGH, persons.pstudent)
    persons['pstudent'] = np.where((persons.SCHG < 1) & (persons.age >= 16), PSTUDENT_NOT, persons.pstudent)
    persons['pstudent'] = np.where((persons.SCHG < 1) & (persons.age < 16), PSTUDENT_GRADE_OR_HIGH, persons.pstudent)
    persons['pstudent'] = np.where((persons.SCHG >= 15) & (persons.age >= 16) & (persons.pemploy != 1), PSTUDENT_UNIVERSITY, persons.pstudent)
    persons['pstudent'] = np.where((persons.SCHG >= 15) & (persons.age < 16) & (persons.pemploy != 1), PSTUDENT_GRADE_OR_HIGH, persons.pstudent)
    persons['pstudent'] = np.where((persons.age <= 19) & (persons.pemploy != 1) & (persons.SCHG >=1) & (persons.SCHG<=14), PSTUDENT_GRADE_OR_HIGH, persons.pstudent)
    persons['pstudent'] = np.where((persons.age > 19) & (persons.pemploy != 1) & (persons.SCHG >=1) & (persons.SCHG<=14),  PSTUDENT_UNIVERSITY, persons.pstudent)
    persons['pstudent'] = np.where(persons.pstudent == 0, 3, persons.pstudent)
    persons['pstudent'] = persons['pstudent'].astype(int)

    PTYPE_FULL, PTYPE_PART, PTYPE_UNIVERSITY, PTYPE_NONWORK, PTYPE_RETIRED, PTYPE_DRIVING, PTYPE_SCHOOL, PTYPE_PRESCHOOL = 1, 2, 3, 4, 5, 6, 7, 8
    persons['ptype'] = np.zeros(len(persons))
    persons['ptype'] = np.where((persons.pemploy == 1),  PTYPE_FULL, PTYPE_NONWORK)
    persons['ptype'] = np.where((persons.pstudent == 3) & (persons.pemploy == 2), PTYPE_PART, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 3) & (persons.age >= 65) & ((persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_RETIRED, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 3) & (persons.age < 6) & ((persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_PRESCHOOL, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 3) & (persons.age >= 6) & (persons.age <= 64) & ((persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_NONWORK, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 2)  & ((persons.pemploy == 2)  | (persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_UNIVERSITY, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 1) & (persons.age < 6)  & ((persons.pemploy == 2)  | (persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_PRESCHOOL, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 1) & (persons.age >= 16)  & ((persons.pemploy == 2)  | (persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_DRIVING, persons.ptype)
    persons['ptype'] = np.where((persons.pstudent == 1) & (persons.age >= 6) & (persons.age < 16)  & ((persons.pemploy == 2)  | (persons.pemploy == 3) | (persons.pemploy == 4)), PTYPE_SCHOOL, persons.ptype)
    persons['ptype'] = persons['ptype'].astype(int)
    
    #revise field of school grade of person: grade
    persons['grade'] = 0
    persons.loc[((persons['SCHG']>=2) & (persons['SCHG']<=10)), 'grade'] = 2
    persons.loc[((persons['SCHG']>=11) & (persons['SCHG']<=14)), 'grade'] = 5
    persons.loc[(persons['SCHG'].isin([15,16])), 'grade'] = 6
    
    #revise hispanic flag field: hisp
    persons['hisp'] = persons['HISP']
    persons.loc[(persons['HISP']!=1), 'hisp'] = 2
    
    #revise miltary field: hisp
    persons['miltary'] = 0
    persons.loc[(persons['MIL']==1), 'miltary'] = 1
    
    #revise educational attainment: educ
    persons['educ'] = np.where(persons.age >= 18, 9, 0)
    persons['educ'] = np.where(persons.age >= 22, 13, persons.educ) #age = years of educ?
    
    #employment related fields
    persons['occen5'] = 0
    persons['indcen'] = 0
    persons.loc[(persons['NAICS2'] == 'MIL'), 'indcen'] = 9770
    
    conditions3 = [((persons["NAICS2"] == '0') | (persons["NAICS2"] == '99')),
                   (persons["NAICS2"].isin(['21','23','48','49','4M','52','53','54','55','56'])),
                   (persons["NAICS2"].isin(['51','61','62','92'])),
                   (persons["NAICS2"].isin(['42','44','45','721','722'])),
                   (persons["NAICS2"].isin(['11','81'])),
                   (persons["NAICS2"].isin(['22','31','32','33','3M','71'])),
                   (persons["NAICS2"] == 'MIL')
                   ]
    choices3 = ['00-0000', '11-1021', '31-1010', '41-1011', '45-1010','51-1011', '55-1010']
    persons["occsoc5"] = pd.Series(np.select(conditions3, choices3, default='00-0000'), dtype="str")
    
    #integer type of fields
    persons['weeks']= persons['weeks'].astype(int)
    persons['hours']= persons['hours'].astype(int)
    persons.fillna(0, inplace=True)
    
    return persons[["hhid", #hhid
                    "perid", #person_id
                    "household_serial_no",
                    "pnum", #pnum
                    "age",
                    "sex",
                    "miltary",
                    "pemploy",
                    "pstudent",
                    "ptype",
                    "educ",
                    "grade",
                    "occen5",
                    "occsoc5",
                    "indcen",
                    "weeks",
                    "hours",
                    "rac1p",
                    "hisp",
                    "version",
                    'naics2_original_code',
                    "soc2"]].sort_values(by=['hhid','pnum','perid'])

# %%
def process_landuse()-> pd.DataFrame:
    '''
        Series15 land use (ABM3) does not contain all of the same columns as ABM2+ land use.
        This function will tranform the Series 15 to match what is expected.
        
        If these column names are changed, then the corresponding names need to be changed in the configs.
    '''
    print('Working on Landuse file')
    df_mgra = pd.read_csv(landuse_file)
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
process_household().to_csv(os.path.join(write_dir, 'households.csv'), index=False)
process_persons().to_csv(os.path.join(write_dir, 'persons.csv'), index=False)
process_landuse().to_csv(os.path.join(write_dir, f'mgra15_based_input{scenario_year}.csv'), index=False)
