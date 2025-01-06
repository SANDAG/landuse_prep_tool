import pandas as pd
import geopandas as gpd
import numpy as np
import yaml
import os

class ConfigLoader:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        with open(self.config_path, 'r') as yamlfile:
            return yaml.load(yamlfile, Loader=yaml.FullLoader)

class DataLoader:
    def __init__(self, config):
        self.config = config
        self.hh_s14 = None
        self.per_s14 = None
        self.mgra_xwalk = None
        self.taz_xwalk = None
        self.landuse_s14 = None
        self.landuse_abm3 = None
        self.input_s15_per = None
        self.random_seed = None
        self.mgra_s14_shp = None
        self.mgra_s15_shp = None
        self.parking_s14 = None
        self.load_data()

    def load_data(self):
        os.chdir(self.config['input']['input_dir'])
        self.hh_s14 = pd.read_csv(self.config['input']['filenames']['households'])
        self.per_s14 = pd.read_csv(self.config['input']['filenames']['persons'])
        self.mgra_xwalk = pd.read_csv(self.config['input']['filenames']['mgra_xwalk'])
        self.taz_xwalk = pd.read_csv(self.config['input']['filenames']['taz_xwalk'])
        self.landuse_s14 = pd.read_csv(self.config['input']['filenames']['land_use'])
        self.landuse_abm3 = pd.read_csv(self.config['input']['filenames']['land_use_abm3'])
        self.input_s15_per =  pd.read_csv(self.config['input']['filenames']['input_s15_per'])
        self.random_seed = self.config['input']['random_seed']
        self.mgra_s14_shp = gpd.read_file(self.config['input']['filenames']['mgra_s14_shp'])
        self.mgra_s15_shp = gpd.read_file(self.config['input']['filenames']['mgra_s15_shp'])
        self.parking_s14 = pd.read_csv(self.config['input']['filenames']['parking_cost_s14'])

class Converter:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.mgra_xwalk_dict = self.data_loader.mgra_xwalk.set_index('MGRA13')['MGRA15'].to_dict()
        self.taz_xwalk_dict = self.data_loader.taz_xwalk.set_index('TAZ13')['TAZ15'].to_dict()
        
    def convert_hh(self):
        hh_s14 = self.data_loader.hh_s14
        hh_s14['mgra'] = hh_s14['mgra'].replace(self.mgra_xwalk_dict)
        hh_s14['taz'] = hh_s14['taz'].replace(self.taz_xwalk_dict)
        hh_s15_converted = hh_s14.rename(columns={'hworkers': 'num_workers'})
        return hh_s15_converted
    
    def convert_per(self):
        per_s15 = self.data_loader.per_s14
        input_s15_per = self.data_loader.input_s15_per
        random_seed = self.data_loader.random_seed
        input_s15_per['naics2_original_code'] = input_s15_per['naics2_original_code'].astype(str)
        input_s15_per['soc2'] = input_s15_per['soc2'].astype(str)
        input_s15_workers = input_s15_per[input_s15_per['pemploy'].isin([1,2])] 
        workers_s15 = per_s15[per_s15['pemploy'].isin([1,2])]
        per_s15[['naics2_original_code','soc2']] = ""
        random_samples = input_s15_workers[['naics2_original_code', 'soc2']].sample(n=len(workers_s15), replace=True, random_state=random_seed)
        per_s15.loc[workers_s15.index, ['naics2_original_code', 'soc2']] = random_samples.values
        per_s15[['naics2_original_code','soc2']] = per_s15[['naics2_original_code','soc2']].replace("","0")
        return per_s15

    def convert_landuse(self, hh_s15_converted, per_s15_converted):
        landuse_s14 = self.data_loader.landuse_s14
        landuse_abm3 = self.data_loader.landuse_abm3
        parking_s14 = self.data_loader.parking_s14
        mgra_s14_shp = self.data_loader.mgra_s14_shp
        mgra_s15_shp = self.data_loader.mgra_s15_shp
        landuse_s15 = pd.DataFrame()
        landuse_s14['mgra_15'] = landuse_s14['mgra'].replace(self.mgra_xwalk_dict)
        
        cols_to_keep_from_abm3 = ['taz', 'luz_id', 'pseudomsa', 'zip09', 'parkactive', 'openspaceparkpreserve', 'beachactive',
                        'district27', 'milestocoast', 'acres', 'land_acres', 'effective_acres', 'truckregiontype', 'nev',
                        'remoteAVParking', 'refueling_stations', 'MicroAccessTime', 'microtransit', 'ech_dist', 'hch_dist']

        landuse_s15 = landuse_abm3[['mgra'] + cols_to_keep_from_abm3].sort_values(by='mgra')


        cols_to_adjust_to_match_synth_pop = ['pop', 'hhp', 'gq_civ', 'gq_mil']
        per_hh_s15 = per_s15_converted.merge(hh_s15_converted[['mgra', 'hhid', 'unittype']], on='hhid', how='left')
        landuse_s15 = (per_hh_s15.groupby('mgra').size().reset_index().rename(columns={0: 'pop'})
                       .merge(landuse_s15, on='mgra', how='right'))

        landuse_s15 = (per_hh_s15[per_hh_s15['unittype'] == 1].groupby(['mgra', 'miltary']).size().unstack().reset_index()
                       .rename(columns={0: 'gq_civ', 1: 'gq_mil'})
                       .merge(landuse_s15, on='mgra', how='right'))

        landuse_s15[['pop', 'gq_mil', 'gq_civ']] = landuse_s15[['pop', 'gq_mil', 'gq_civ']].fillna(0)
        landuse_s15['hhp'] = landuse_s15['pop'] - landuse_s15['gq_civ'] - landuse_s15['gq_mil']
        landuse_s15[cols_to_adjust_to_match_synth_pop] = landuse_s15[cols_to_adjust_to_match_synth_pop].round(0).astype(int)

        cols_to_calc_from_synth_pop = ['hh_mf', 'hh_mh', 'hh_sf', 'hh']
        bldgsz_map = {0: 'hh_mf', 1: 'hh_mh', 2: 'hh_sf', 3: 'hh_sf', 4: 'hh_mf', 5: 'hh_mf', 6: 'hh_mf', 7: 'hh_mf', 8: 'hh_mf', 9: 'hh_mf', 10: 'hh_mh'}
        gb = (hh_s15_converted[['mgra', 'bldgsz']]
              .assign(bldgsz_rm=lambda df: df['bldgsz'].replace(bldgsz_map))
              .groupby(['mgra', 'bldgsz_rm']).size().unstack(fill_value=0).reset_index())
        gb['hh'] = gb[['hh_mf', 'hh_mh', 'hh_sf']].sum(axis=1)
        landuse_s15 = landuse_s15.merge(gb, on='mgra', how='left')
        landuse_s15[cols_to_calc_from_synth_pop] = landuse_s15[cols_to_calc_from_synth_pop].fillna(0).astype(int)

        landuse_s15['hhs'] = landuse_s15.apply(lambda row: round(row['hhp'] / row['hh'], 3) if row['hh'] != 0 else 0, axis=1)

        inc_cols = ['i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9', 'i10']
        abm3_i_shares = landuse_abm3[['mgra']].copy()
        temp = landuse_abm3[['mgra'] + inc_cols + ['hh']]

        for col in inc_cols:
            abm3_i_shares[f'{col}_pct'] = temp.apply(lambda row: row[col] / row['hh'] if row['hh'] != 0 else 0, axis=1)

        for col in inc_cols:
            landuse_s15[col] = landuse_s15['hh'] * abm3_i_shares[f'{col}_pct'].values

        landuse_s15[inc_cols] = landuse_s15[inc_cols].round(0).astype(int)

        emp_adj_fac = landuse_abm3['emp_total'].sum() / landuse_s14['emp_total'].sum()
        temp = (landuse_s14.groupby('mgra_15')['emp_total'].sum()
                .reset_index()
                .assign(emp_total=lambda df: df['emp_total'] * emp_adj_fac))

        landuse_s15 = landuse_s15.merge(temp, left_on='mgra', right_on='mgra_15', how='left')

        emp15_cols = [x for x in landuse_abm3.columns if x.startswith('emp_') and x != 'emp_total']
        amb3_emp_shares_taz = (landuse_abm3[['taz']].drop_duplicates().sort_values(by='taz')
                               .merge(landuse_abm3.groupby('taz')[emp15_cols + ['emp_total']].sum().reset_index(), on='taz', how='left'))

        for col in emp15_cols:
            amb3_emp_shares_taz[f'{col}_pct'] = amb3_emp_shares_taz[col] / amb3_emp_shares_taz['emp_total']

        amb3_emp_shares_mgra = landuse_abm3[['mgra', 'taz']].merge(amb3_emp_shares_taz, on='taz', how='left')

        for col in emp15_cols:
            landuse_s15[col] = amb3_emp_shares_mgra[f'{col}_pct'] * landuse_s15['emp_total']

        landuse_s15[emp15_cols] = landuse_s15[emp15_cols].fillna(0).round(0).astype(int)
        landuse_s15['emp_total'] = landuse_s15[emp15_cols].sum(axis=1)

        cols = ['hs', 'hs_sf', 'hs_mf', 'hs_mh', 'enrollgradekto8', 'enrollgrade9to12', 'collegeenroll', 'othercollegeenroll', 'hotelroomtotal']
        landuse_s15 = landuse_s14.groupby('mgra_15')[cols].sum().merge(landuse_s15, right_on='mgra', left_on=['mgra_15'], how='right')
        landuse_s15[cols] = landuse_s15[cols].fillna(0).astype(int)

        landuse_s15 = landuse_s15.drop(columns=['mgra_15', ]).fillna(0)
        cols_order = [col for col in landuse_abm3.columns if col in landuse_s15.columns]
        landuse_s15 = landuse_s15[cols_order]
        
        parking_s15 = self._parking_conversion(mgra_s14_shp, mgra_s15_shp, parking_s14, landuse_s14)
        landuse_s15 = landuse_s15.merge(parking_s15, on='mgra', how='left').fillna(0)
        landuse_s15.loc[landuse_s15['mgra'] == 6895, 'parking_type'] = 3
        return landuse_s15
    
    def _min_parkarea(self, group, park_area_s14):
            group['area_pct'] = group['area']/group['area'].sum()
            mgra14_list = group.loc[group['area_pct'] > 0.1, 'mgra_14']
            if mgra14_list.empty:
                return None 
            return park_area_s14[mgra14_list].min()
    
    def _parking_conversion(self, mgra_s14_shp, mgra_s15_shp, parking_s14, landuse_s14):
        mgra_s15_shp = mgra_s15_shp.to_crs(epsg=2230) if not mgra_s15_shp.crs.is_projected else mgra_s15_shp
        mgra_s14_shp = mgra_s14_shp.to_crs(epsg=2230) if not mgra_s14_shp.crs.is_projected else mgra_s14_shp
        mgra_s14_shp = mgra_s15_shp.to_crs(mgra_s15_shp.crs) if mgra_s15_shp.crs != mgra_s14_shp.crs else mgra_s14_shp
        
        mgra_s15_shp = mgra_s15_shp.rename(columns={'MGRA':'mgra_15'})
        mgra_s14_shp = mgra_s14_shp.rename(columns={'MGRA':'mgra_14'})
        
        landuse_s14['parking_spaces'] = landuse_s14[['hstallsoth', 'hstallssam', 'dstallsoth', 'dstallssam', 'mstallsoth', 'mstallssam']].max(axis=1)
        parking_stalls_s15 = landuse_s14.groupby('mgra_15')['parking_spaces'].sum()
        
        mgra15_over_mgra14 = gpd.overlay(mgra_s15_shp, mgra_s14_shp, how='intersection')
        mgra15_over_mgra14['area'] = mgra15_over_mgra14['geometry'].area

        largest_area = mgra15_over_mgra14.loc[mgra15_over_mgra14.groupby('mgra_15')['area'].idxmax(), ['mgra_15', 'mgra_14']]
        parking_costs_s15 = largest_area.merge(parking_s14, right_on='mgra', left_on='mgra_14', how='left')
        parking_costs_s15 = (parking_costs_s15.drop(columns = ['mgra_14', 'mgra', 'mgraParkArea'])
                                            .rename(columns={'mgra_15':'mgra',
                                                            'lsWgtAvgCostM':'exp_monthly',
                                                            'lsWgtAvgCostD':'exp_daily',
                                                            'lsWgtAvgCostH':'exp_hourly'})                    
        )
        
        park_area_s14 = parking_s14.set_index('mgra')['mgraParkArea']
        min_park_area = mgra15_over_mgra14.groupby('mgra_15').apply(lambda group: self._min_parkarea (group, park_area_s14))
        
        parking_costs_s15['parking_type'] = parking_costs_s15['mgra'].map(min_park_area)
        parking_costs_s15['parking_type'] = np.where(parking_costs_s15['parking_type'].isin([3,4]), np.nan, parking_costs_s15['parking_type'])

        parking_costs_s15['parking_type'] = np.where(
            ((parking_costs_s15['exp_monthly'] + parking_costs_s15['exp_hourly'] + parking_costs_s15['exp_hourly']) != 0) & parking_costs_s15['parking_type'].isna(),
            1,
            parking_costs_s15['parking_type']
        )
        parking_costs_s15['parking_type'] = parking_costs_s15['parking_type'].fillna(3).astype(int)
        parking_s15 = pd.merge(parking_stalls_s15, parking_costs_s15, right_on='mgra', left_index=True, how='outer').fillna(0)
        return parking_s15

class Main:
    def __init__(self, config_path):
        self.config_loader = ConfigLoader(config_path)
        self.data_loader = DataLoader(self.config_loader.config)
        self.converter = Converter(self.data_loader)

    def run(self):
        hh_s15 = self.converter.convert_hh()
        per_s15 = self.converter.convert_per()
        landuse_s15 = self.converter.convert_landuse(hh_s15, per_s15)
        
        os.chdir(self.config_loader.config['output']['output_dir'])
        hh_s15.to_csv(self.config_loader.config['output']['filenames']['households'], index=False)
        per_s15.to_csv(self.config_loader.config['output']['filenames']['persons'], index=False)
        landuse_s15.to_csv(self.config_loader.config['output']['filenames']['land_use'], index=False)

if __name__ == "__main__":
    main = Main('config.yaml')
    main.run()