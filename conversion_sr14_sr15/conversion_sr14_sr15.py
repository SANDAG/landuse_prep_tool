#%%
import pandas as pd
import yaml
import os

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
def convert_hh(hh_s14):
    hh_s14['mgra'] = hh_s14['mgra'].replace(mgra_xwalk_dict)
    hh_s14.rename(columns = {'hworkers':'num_workers'}, inplace = True)
    return hh_s14

def convert_per(per_s14):
    per_s14.rename(columns={'miltary':'military'}, inplace = True)
    per_s14.drop(columns=['indcen', 'weeks', 'hours', 'rac1p', 'hisp', 'version'], inplace=True)
    return per_s14 

def convert_landuse(landuse_s14, landuse_abm3):
    ## CODE FROM LAND USE CONVERSION SECTION TO BE ADDED HERE POTENTIALLY 
    return 
    
# CONVERT TO S15
hh_s15 = convert_hh(hh_s14)
per_s15 = convert_per(per_s14)
#landuse_s15 = convert_landuse(landuse_s14, landuse_abm3) 

#%% LAND USE CONVERSION
# Initializing dataframes
landuse_s15 = pd.DataFrame()
landuse_s14['mgra_15'] = landuse_s14['mgra'].replace(mgra_xwalk_dict)

# MGRA
landuse_s15['mgra'] = landuse_abm3['mgra']
landuse_s15.sort_values(by='mgra', inplace=True)

# TAZ, luz_id, zip09, pseudomsa, parkactive,, beachactive, openspaceparkpreserve, district27
cols_to_keep= ['taz','luz_id', 'pseudomsa', 'zip09', 'parkactive', 'openspaceparkpreserve', 'beachactive',
               'district27', 'milestocoast', 'acres', 'land_acres', 'effective_acres', 'truckregiontype', 'nev',
               'remoteAVParking', 'refueling_stations', 'MicroAccessTime', 'microtransit', 'ech_dist', 'hch_dist']

landuse_s15 = landuse_s15.merge(landuse_abm3[['mgra'] + cols_to_keep], on='mgra')

# Pop, hhp, gq_civ, gq_mil
cols = ['pop', 'hhp', 'gq_civ', 'gq_mil']
per_hh_s15 = per_s15.merge(hh_s15[['mgra', 'hhid', 'unittype']], on='hhid', how='left')
landuse_s15 = (per_hh_s15.groupby('mgra').size().reset_index().rename(columns={0:'pop'})
                      .merge(landuse_s15, on='mgra', how='right')
)

landuse_s15 = (per_hh_s15[per_hh_s15['unittype']==1].groupby(['mgra', 'military']).size().unstack().reset_index()
                                                    .rename(columns={0:'gq_civ', 1:'gq_mil'})
                                                    .merge(landuse_s15, on='mgra', how='right')
)

landuse_s15[['pop', 'gq_mil', 'gq_civ']] = landuse_s15[['pop', 'gq_mil', 'gq_civ']].fillna(0)
landuse_s15['hhp'] = landuse_s15['pop'] - landuse_s15['gq_civ'] - landuse_s15['gq_mil']
landuse_s15[cols] = landuse_s15[cols].round(0).astype(int)

# hh, hh_sf, hh_mf, hh_mh  
bldgsz_map = {0:'hh_mf',1: 'hh_mh', 2: 'hh_sf', 3: 'hh_sf', 4:'hh_mf', 5:'hh_mf', 6:'hh_mf', 7:'hh_mf', 8: 'hh_mf', 9: 'hh_mf', 10: 'hh_mh'}
gb = (hh_s15[['mgra', 'bldgsz']]
      .assign(bldgsz_rm = lambda df: df['bldgsz'].replace(bldgsz_map))
      .groupby(['mgra', 'bldgsz_rm']).size().unstack(fill_value=0).reset_index())
gb['hh'] = gb[['hh_mf', 'hh_mh', 'hh_sf']].sum(axis=1)
landuse_s15 = landuse_s15.merge(gb, on='mgra', how='left')
landuse_s15[['hh_mf', 'hh_mh', 'hh_sf', 'hh']] = landuse_s15[['hh_mf', 'hh_mh', 'hh_sf', 'hh']].fillna(0).astype(int)
    
# hhs
landuse_s15['hhs'] = landuse_s15.apply(lambda row: round(row['hhp']/row['hh'],3) if row['hh']!=0 else 0, axis = 1)
    
# income categories
inc_cols = ['i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9', 'i10']
abm3_i_shares = landuse_abm3[['mgra']].copy()
temp = landuse_abm3[['mgra'] + inc_cols + ['hh']]

for col in inc_cols:
    abm3_i_shares[f'{col}_pct'] = temp.apply(lambda row: row[col]/row['hh'] if row['hh']!=0 else 0, axis=1)
    
for col in inc_cols:
    landuse_s15[col] = landuse_s15['hh']*abm3_i_shares[f'{col}_pct'].values
    
landuse_s15[inc_cols] = landuse_s15[inc_cols].round(0).astype(int)    
    
# employment categories 
emp_adj_fac = landuse_abm3['emp_total'].sum()/landuse_s14['emp_total'].sum()
temp = (landuse_s14.groupby('mgra_15')['emp_total'].sum()
                    .reset_index()
                    .assign(emp_total = lambda df: df['emp_total']*emp_adj_fac)) 

landuse_s15 = landuse_s15.merge(temp, left_on='mgra', right_on='mgra_15', how = 'left')

emp15_cols = [x for x in landuse_abm3.columns if x.startswith('emp_') and x != 'emp_total']
amb3_emp_shares_taz = ( landuse_abm3[['taz']].drop_duplicates().sort_values(by='taz')
                                         .merge(landuse_abm3.groupby('taz')[emp15_cols + ['emp_total']].sum().reset_index(), on='taz', how='left')
)

for col in emp15_cols:
    amb3_emp_shares_taz[f'{col}_pct'] = amb3_emp_shares_taz[col] / amb3_emp_shares_taz['emp_total']

amb3_emp_shares_mgra = landuse_abm3[['mgra', 'taz']].merge(amb3_emp_shares_taz, on='taz', how='left')

for col in emp15_cols:
    landuse_s15[col] = amb3_emp_shares_mgra[f'{col}_pct'] * landuse_s15['emp_total']

landuse_s15[emp15_cols] = landuse_s15[emp15_cols].fillna(0).round(0).astype(int)
landuse_s15['emp_total'] = landuse_s15[emp15_cols].sum(axis=1)

# housing structures, enrollment, hotelroomtotal
cols = ['hs', 'hs_sf', 'hs_mf', 'hs_mh','enrollgradekto8', 'enrollgrade9to12', 'collegeenroll', 'othercollegeenroll','hotelroomtotal']
landuse_s15 = landuse_s14.groupby('mgra_15')[cols].sum().merge(landuse_s15, right_on='mgra', left_on=['mgra_15'], how='right')
landuse_s15[cols] = landuse_s15[cols].fillna(0).astype(int)

# Rearranging/cleaning columns
landuse_s15 = landuse_s15.drop(columns = ['mgra_15',]).fillna(0)
cols_order = [col for col in landuse_abm3.columns if col in landuse_s15.columns]
landuse_s15 = landuse_s15[cols_order]

#%% OUTPUT
os.chdir(config['output']['output_dir'])
hh_s15.to_csv(config['output']['filenames']['households'], index=False)
per_s15.to_csv(config['output']['filenames']['persons'], index=False)
landuse_s15.to_csv(config['output']['filenames']['land_use'], index=False)
