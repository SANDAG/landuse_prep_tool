#%%
import pandas as pd
import yaml
import os

os.chdir('../scripts')

# LOAD CONFIGS
with open('config.yaml', 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

# LOAD INPUT FILES
os.chdir(config['input']['input_dir'])

hh_s14 = pd.read_csv(config['input']['filenames']['households'])
per_s14 = pd.read_csv(config['input']['filenames']['persons'])
mgra_xwalk = pd.read_csv(config['input']['filenames']['mgra_xwalk'])
landuse_s14 = pd.read_csv(config['input']['filenames']['land_use'])
landuse_abm3 = pd.read_csv(config['input']['filenames']['land_use_abm3'])

mgra_xwalk_dict = mgra_xwalk.set_index('MGRA13')['MGRA15'].to_dict()

# FUNCTIONS
def convert_hh(df):
    df['mgra'] = df['mgra'].replace(mgra_xwalk_dict)
    df.rename(columns = {'hworkers':'num_workers'}, inplace = True)
    return df

def convert_per(df):
    df.rename(columns={'miltary':'military'}, inplace = True)
    df.drop(columns=['indcen', 'weeks', 'hours', 'rac1p', 'hisp', 'version'], inplace=True)
    return df 

def calculate_shares(df, col_name):
    tot_col = df[col_name].sum()
    df[f'{col_name}_pct'] = df[col_name] / tot_col
    return df[['mgra_15', f'{col_name}_pct']]

def convert_landuse(df):
    ## CODE FROM LAND USE CONVERSION SECTION TO BE ADDED HERE
    
# CONVERT TO S15
hh_s15 = convert_hh(hh_s14)
per_s15 = convert_per(per_s14)

#%% LAND USE CONVERSION
# Initializing dataframes
landuse_s15 = pd.DataFrame()
landuse_s14['mgra_15'] = landuse_s14['mgra'].replace(mgra_xwalk_dict)

# ABM3 landuse with only TAZs in ABM2+
landuse_abm3s = (landuse_abm3[landuse_abm3['mgra'].isin(landuse_s14['mgra_15'].unique())]
                 .sort_values(by='mgra'))

# MGRA
landuse_s15['mgra_15'] = landuse_s14['mgra_15'].unique()
landuse_s15.sort_values(by='mgra_15', inplace=True)

# TAZ, luz_id, zip09, pseudomsa, parkactive,, beachactive, openspaceparkpreserve, district27
cols_to_keep= ['taz','luz_id', 'pseudomsa', 'zip09', 'parkactive', 'openspaceparkpreserve', 'beachactive',
               'district27', 'milestocoast', 'acres', 'land_acres', 'effective_acres', 'truckregiontype', 'nev',
               'remoteAVParking', 'refueling_stations', 'MicroAccessTime', 'microtransit', 'ech_dist', 'hch_dist']

landuse_s15 = landuse_s15.merge(landuse_abm3[['mgra'] + cols_to_keep], left_on='mgra_15', right_on='mgra').drop(columns = ['mgra'])

# Pop, hhp, gq_civ, gq_mil
cols = ['pop', 'hhp', 'gq_civ', 'gq_mil']
pop_adj_factor = per_s14.shape[0]/landuse_s14['pop'].sum()  
landuse_s15 = (landuse_s14[['mgra_15'] + cols].groupby('mgra_15').sum().reset_index()
                                              .merge(landuse_s15, on='mgra_15', how='right'))
for col in cols:
    landuse_s15[f'{col}'] = landuse_s15[col]*pop_adj_factor   

# hh, hh_sf, hh_mf, hh_mh  
bldgsz_map = {1: 'hh_mh', 2: 'hh_sf', 3: 'hh_sf', 8: 'hh_mf', 9: 'hh_mf'}
gb = (hh_s15[['mgra', 'bldgsz']]
      .assign(bldgsz_rm = lambda df: df['bldgsz'].map(bldgsz_map))
      .groupby(['mgra', 'bldgsz_rm']).size().unstack(fill_value=0).reset_index())
gb['hh'] = gb[['hh_mf', 'hh_mh', 'hh_sf']].sum(axis=1)
landuse_s15 = landuse_s15.merge(gb, right_on='mgra',left_on='mgra_15', how='left').drop(columns = ['mgra'])

# hs, hs_sf, hs_mf, hs_mh
hs_to_hh = (landuse_abm3s['hs']/landuse_abm3s['hh']).fillna(0)
landuse_s15['hs'] = landuse_s15['hh']*hs_to_hh.values

for col in ['hs_sf', 'hs_mf', 'hs_mh']:
    ratio = (landuse_abm3s[col]/landuse_abm3s['hs']).fillna(0)
    landuse_s15[col] = landuse_s15['hs']*ratio.values
    
# hhs
landuse_s15 = (hh_s15.groupby('mgra')['persons'].mean()
               .reset_index().rename(columns = {'persons':'hhs'})
               .merge(landuse_s15, left_on='mgra', right_on='mgra_15', how='right').drop(columns = ['mgra']))
    
# income categories
i_cols = ['i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9', 'i10']
abm3_i_shares = landuse_abm3s[['mgra']].copy()
temp = landuse_abm3s[['mgra'] + i_cols + ['hh']]

for col in i_cols:
    abm3_i_shares[f'{col}_pct'] = temp.apply(lambda row: row[col]/row['hh'] if row['hh']!=0 else 0, axis=1)
    
for col in i_cols:
    landuse_s15[col] = landuse_s15['hh']*abm3_i_shares[f'{col}_pct'].values
    
# employment categories 
s14_emp_total = landuse_s14.groupby('mgra_15')['emp_total'].sum().reset_index()
s14_emp_pct = calculate_shares(s14_emp_total, 'emp_total')
landuse_s15['emp_total'] = s14_emp_pct['emp_total_pct']*landuse_abm3['emp_total'].sum()

amb3_emp_shares = landuse_abm3[['mgra']].copy()
emp15_cols = [x for x in landuse_abm3.columns if x.startswith('emp_') and x != 'emp_total']
temp = landuse_abm3[['mgra'] + emp15_cols + ['emp_total']]

for col in emp15_cols:
    amb3_emp_shares[f'{col}_pct'] = temp.apply(lambda row: row[col]/row['emp_total'] if row['emp_total'] != 0 else 0, axis = 1)

for col in emp15_cols:
    landuse_s15[col] = amb3_emp_shares[f'{col}_pct']*landuse_s15['emp_total']   
    adj_factor = landuse_abm3[col].sum()/landuse_s15[col].sum()
    landuse_s15[col] = landuse_s15[col]*adj_factor

# enrollment, hotelroomtotal
col = ['enrollgradekto8', 'enrollgrade9to12', 'collegeenroll', 'othercollegeenroll','hotelroomtotal']
landuse_s15 = landuse_s14.groupby('mgra_15')[col].sum().merge(landuse_s15, on='mgra_15', how='right')

# Rearranging/cleaning columns
landuse_s15.rename(columns = {'mgra_15':'mgra'}, inplace = True)
cols_order = [col for col in landuse_abm3.columns if col in landuse_s15.columns]
landuse_s15 = landuse_s15[cols_order]
landuse_s15 = landuse_s15.fillna(0)

#%% OUTPUT
os.chdir(config['output']['output_dir'])
hh_s15.to_csv(config['output']['filenames']['households'], index=False)
per_s15.to_csv(config['output']['filenames']['persons'], index=False)
landuse_s15.to_csv(config['output']['filenames']['land_use'], index=False)