# %%
import numpy as np
import os
import pandas as pd
import geopandas as gpd
import sys
import yaml

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
scenario_year = cfg['scenario_year']
write_dir = cfg['output_dir']
EF_dir = cfg['EF_dir']

# %%
households_file = os.path.join(EF_dir,cfg['households_file'].replace('${scenario_year}', str(scenario_year)))
persons_file = os.path.join(EF_dir,cfg['persons_file'].replace('${scenario_year}', str(scenario_year)))
landuse_file = os.path.join(EF_dir,cfg['landuse_file'].replace('${scenario_year}', str(scenario_year)))
# parking_file = os.path.join(input_dir,cfg['parking_file'].replace('${scenario_year}', str(scenario_year)))
# parking_file = os.path.join(input_dir,cfg['parking_file'])
micro_mobility_file = os.path.join(input_dir,cfg['micro_mob_file'])
hub_mgra_map_file = os.path.join(input_dir,cfg['hubs_mapping'])
auxiliary_file = os.path.join(input_dir,cfg['auxiliary_file']) #2019 school, remoteAVParking	refueling_stations

microtransit_file = os.path.join(input_dir,cfg['microtransit_file'])
with open(microtransit_file, "r") as f:
    microtransit = yaml.safe_load(f)
    f.close()  #MicroTransit changes 

#########################################################################
# out_dir = settings.get("output_dir")
# inputs = settings.get('inputs')
method = cfg["space_estimation_method"]
geometry = os.path.join(input_dir,cfg["geometry"])
lu_path = landuse_file
imputed_parking_file = os.path.join(input_dir,cfg["imputed_parking_df"])
imputed_parking_df = pd.read_csv(imputed_parking_file).set_index('mgra')
lu_df = pd.read_csv(lu_path).set_index("mgra")
print("Reading MGRA shapefile data")
path = geometry
mgra_gdf = gpd.read_file(path).set_index("MGRA")[ #mgra index removed
    ["TAZ", "geometry"]
]
street_file = os.path.join(input_dir,cfg["street_file"])
street_data = pd.read_csv(street_file).set_index("MGRA")
param_file = os.path.join(input_dir,cfg["model_params"])
model_params = pd.read_csv(param_file)
max_dist = cfg["walk_dist"]
walk_coef = cfg["walk_coef"]
#########################################################################
#Parking File Creation
districts_df = park_func.create_districts(imputed_parking_df,mgra_gdf,max_dist)
estimated_space_df = park_func.create_spaces_df(mgra_gdf,lu_df,street_data,model_params,imputed_parking_df,method)
exp_prkcosts_df = park_func.run_expected_parking_cost(max_dist,walk_coef,districts_df,mgra_gdf,imputed_parking_df,estimated_space_df)

parking_df = exp_prkcosts_df.join(districts_df['parking_type']).join(imputed_parking_df['spaces_reduction'])
parking_df['spaces_reduction'].fillna(0,inplace=True)
parking_df.rename(columns={'spaces_reduction':'parking_spaces'},inplace=True)
parking_df.index = parking_df.index.set_names('mgra')
# parking_df.to_csv('./parking_file.csv')
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
    
    #create poverty (ref: ASPE)
    households['poverty_guideline'] = 12760
    households.loc[(households['persons'] == 2), 'poverty_guideline'] = 17240
    households.loc[(households['persons'] == 3), 'poverty_guideline'] = 21720
    households.loc[(households['persons'] == 4), 'poverty_guideline'] = 26200
    households.loc[(households['persons'] == 5), 'poverty_guideline'] = 30680
    households.loc[(households['persons'] == 6), 'poverty_guideline'] = 35160
    households.loc[(households['persons'] == 7), 'poverty_guideline'] = 39640
    households.loc[(households['persons'] == 8), 'poverty_guideline'] = 44120
    households.loc[(households['persons'] >= 9), 'poverty_guideline'] = 44120 + 4480* (households['persons']-8)
    
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
    # df_parking = pd.read_csv(parking_file)
    mmfile = pd.read_csv(micro_mobility_file)
    hubs_map = pd.read_csv(hub_mgra_map_file)
    df_auxiliary = pd.read_csv(auxiliary_file)


    #Mapping mobility hubs to mgra
    mmfile = mmfile[['Mobility_Hub','Access_Time']].set_index('Mobility_Hub')
    # mmfile['Access_Time'].fillna(0,inplace=True)  #Comment this out for removing 0 from micro access time
    hubs_map['MicroAccessTime'] = hubs_map['MoHubName'].map(mmfile['Access_Time'])
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
    merged_df = pd.merge(merged_df,hubs_map[['MGRA','MicroAccessTime']], left_on='mgra', right_on='MGRA', how='left')
    merged_df = merged_df.drop('MGRA', axis=1)
    merged_df['MicroAccessTime'].fillna(999,inplace=True)
    merged_df['MicroAccessTime']= merged_df['MicroAccessTime'].astype(int)

    merged_df["microtransit"] = np.zeros(len(merged_df), int)
    merged_df["nev"] = np.zeros(len(merged_df), int)
    for service, info in microtransit['services'].items():
        for mgra_serviced in info['mgras_serviced']:
            # Find the row in the DataFrame where mgra matches
            match_row = merged_df[merged_df['mgra'] == mgra_serviced]
            if not match_row.empty:
                merged_df.loc[match_row.index, info['type']] = info['id']

    return merged_df.sort_values(by='mgra')

# %%
process_household().to_csv(os.path.join(write_dir, 'households.csv'), index=False)
process_persons().to_csv(os.path.join(write_dir, 'persons.csv'), index=False)
process_landuse().to_csv(os.path.join(write_dir, f'mgra15_based_input{scenario_year}.csv'), index=False)