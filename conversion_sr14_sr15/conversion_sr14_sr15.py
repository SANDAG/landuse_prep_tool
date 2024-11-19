import pandas as pd
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
        input_s15_per['naics2_original_code'] = input_s15_per['naics2_original_code'].astype(str)
        input_s15_per['soc2'] = input_s15_per['soc2'].astype(str)
        input_s15_workers = input_s15_per[input_s15_per['pemploy'].isin([1,2])] 
        workers_s15 = input_s15_per[input_s15_per['pemploy'].isin([1,2])]
        per_s15[['naics2_original_code','soc2']] = ""
        random_samples = input_s15_workers[['naics2_original_code', 'soc2']].sample(n=len(workers_s15), replace=True)
        per_s15.loc[workers_s15.index, ['naics2_original_code', 'soc2']] = random_samples.values
        per_s15[['naics2_original_code','soc2']] = per_s15[['naics2_original_code','soc2']].replace("","0")
        return per_s15

    def convert_landuse(self, hh_s15_converted, per_s15_converted):
        landuse_s14 = self.data_loader.landuse_s14
        landuse_abm3 = self.data_loader.landuse_abm3
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

        return landuse_s15

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