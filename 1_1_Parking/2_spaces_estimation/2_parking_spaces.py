import osmnx as ox
import geonetworkx as gnx
import networkx as nx
import geopandas as gpd
import pandas as pd
import statsmodels.formula.api as smf
from tqdm import tqdm
import yaml
import os
import pickle

config = './2_setting_spaces.yaml'
# config = './settings_inventory.yaml'
with open(config, "r") as stream:
    try:
        settings = yaml.load(stream, Loader=yaml.FullLoader)
        
        print(stream)
    except yaml.YAMLError as exc:
        print("ERRRORRR")
        print(exc)

inputs = settings.get('inputs')        
geometry = inputs.get("geometry")
base_lu_path = inputs.get("base_lu")
# lu_path = inputs.get("land_use")
imputed_parking_file = inputs.get("imputed_parking_df")
imputed_parking_df = pd.read_csv(imputed_parking_file).set_index('mgra')
bike_net = inputs.get('bike_net')
bike_node = inputs.get('bike_node')

base_lu_df = pd.read_csv(base_lu_path).set_index("mgra")
# lu_df = pd.read_csv(lu_path).set_index("mgra")
print("Reading MGRA shapefile data")
path = geometry
mgra_gdf = gpd.read_file(path)[ #mgra index removed
    ["MGRA","TAZ", "geometry"]
]
def run_space_estimation():
    method = settings.get("space_estimation_method")
    cache_dir = settings.get("cache_dir")

    assert isinstance(mgra_gdf, gpd.GeoDataFrame)
    assert isinstance(imputed_parking_df, pd.DataFrame)
    assert isinstance(base_lu_df, pd.DataFrame)

    parking_df = imputed_parking_df[["paid_spaces","free_spaces","total_spaces"]]
    street_data = get_streetdata(mgra_gdf)
    street_data["estimated_spaces"] = model_fit(
        street_data, parking_df, mgra_gdf, base_lu_df
    )

def get_streetdata(mgra_gdf):        
    out_dir = settings.get("output_dir")
    cache_dir = settings.get("cache_dir")
    data_path = os.path.join(out_dir, 'aggregated_street_data.csv')
    
    #Fetch from local if available
    if not os.path.isfile(data_path):
        print("Aggregating street data")
        node_gdf,edge_gdf = get_filter_network(cache_dir)

        # Aggregate length and number of intersections per zone
        street_data = aggregate_streetdata(node_gdf, edge_gdf, mgra_gdf)
                    
        df = street_data[["length", "intcount"]]
        assert isinstance(df, pd.DataFrame)
        df.to_csv(data_path)
    else:
        street_data = pd.read_csv(data_path).set_index("MGRA")

    street_data = street_data

    return street_data

#Getting the network and node shapefile from settings
def get_filter_network(cache_path):
    print('Reading network and nodes file')
    node_gdf = gpd.read_file(bike_node)[['NodeLev_ID','XCOORD','YCOORD','ZCOORD',"geometry"]]
    network_gdf = gpd.read_file(bike_net)[['A','B','Distance',"geometry",'ABBikeClas',
                                       'BABikeClas','Func_Class']]
    
    #Filter all highways, private roads, paper st, rural mountain roads
    func_class_to_exclude = [-1,0,3,10]
    network_gdf = network_gdf[~network_gdf['Func_Class'].isin(func_class_to_exclude)]
    network_gdf = network_gdf[~network_gdf['ABBikeClas'].isin([1])]
    network_gdf = network_gdf[~network_gdf['BABikeClas'].isin([1])]

    return node_gdf,network_gdf

#
def aggregate_streetdata(node_gdf, edge_gdf, mgra_gdf):
    buffer_radius = 0.00001  # Adjust buffer radius as needed
    node_gdf['geometry'] = node_gdf['geometry'].buffer(buffer_radius)

    # Spatial join to count the number of links intersecting each node
    nodes_with_street_count = gpd.sjoin(node_gdf, edge_gdf, how='left', predicate='intersects')

    # Group by node ID and count the number of streets n street_count>2
    street_count = nodes_with_street_count.groupby('NodeLev_ID').size()
    nodes_with_greater_than_2_streets = street_count[street_count > 2].index

    # Subset nodes GeoDataFrame to get nodes with street count > 2
    intnodes_gdf = node_gdf[node_gdf['NodeLev_ID'].isin(nodes_with_greater_than_2_streets)]

    def intersect_zones(geo):
        # First clip search space
        edges_clipped = gpd.clip(edge_gdf, geo)
        nodes_clipped = gpd.clip(intnodes_gdf, geo)

        # Get detailed intersection
        e = edges_clipped.geometry.intersection(geo)
        n = nodes_clipped.geometry.intersection(geo)
        # Remove empty
        e = e[~e.is_empty]

        res = {
            "length": e.length.sum(),
            "intcount": n.count(),
            "edges": e,
            "nodes": n,
        }
        return res

    print("Aggregating network data into zones")
    street_data = [intersect_zones(x) for x in tqdm(list(mgra_gdf.geometry.values))]
    streets_gdf = gpd.GeoDataFrame.from_dict(street_data)
    streets_gdf.index = mgra_gdf['MGRA']

    return streets_gdf


def model_fit(street_data, parking_df, mgra_gdf, land_use):
    out_dir = settings.get("output_dir")
    mgra_gdf1 = mgra_gdf.copy().set_index("MGRA") #Joining based on index
    acres = (mgra_gdf1.geometry.area / 43560).to_frame("acres")
    lu = land_use[["hh", "hh_sf", "hh_mf", "emp_total"]]

    model_df = parking_df.join(street_data[["length", "intcount"]])
    model_df = model_df.join(acres)
    model_df["length_per_acre"] = model_df.length / model_df.acres
    model_df["int_per_acre"] = model_df.intcount / model_df.acres
    model_df["avg_block_length"] = model_df.length / model_df.intcount.clip(1)
    model_df = model_df.join(land_use[["hh", "hh_sf", "hh_mf", "emp_total"]])

    # Free spaces model fit
    model_df_free = model_df[(model_df.free_spaces > 0) & (model_df.length > 0)] 
    model_df_paid = model_df[(model_df.paid_spaces > 0) & (model_df.length > 0)]
    # model_df_total = model_df[(model_df.total_spaces > 0) & (model_df.length > 0)]
    
    # Formula
    f_free = "free_spaces ~ 0 + length + intcount + hh_sf + hh_mf + emp_total"
    f_paid = "paid_spaces ~ 0 + length + intcount + acres + hh_sf + emp_total"
    # f_total = "total_spaces ~ 0 + length + intcount + acres + hh_sf + hh_mf + emp_total"

    # Estimate model
    mod_lm_free = smf.ols(formula=f_free, data=model_df_free).fit()
    mod_lm_paid = smf.ols(formula=f_paid, data=model_df_paid).fit()
    # mod_lm_total = smf.ols(formula=f_total, data=model_df_total).fit()


    # Create summaries
    summary1 = mod_lm_free.summary()
    summary2 = mod_lm_paid.summary()
    # summary3 = mod_lm_total.summary()

    # Convert summaries to dataframes
    # summary_df1 = pd.DataFrame(summary1.tables[1])
    # summary_df2 = pd.DataFrame(summary2.tables[1])
    # # summary_df3 = pd.DataFrame(summary3.tables[1])
    # summary_df1['R-squared'] = mod_lm_free.rsquared
    # summary_df2['R-squared'] = mod_lm_paid.rsquared
    # # summary_df3['R-squared'] = mod_lm_total.rsquared

    # # Save dataframes to Excel
    # with pd.ExcelWriter(os.path.join(out_dir, 'spaces_ols_summaries1.xlsx')) as writer:
    #     summary_df1.to_excel(writer, sheet_name='Free Spaces Summary', index=False)
    #     summary_df2.to_excel(writer, sheet_name='Paid Spaces Summary', index=False)
    #     summary_df3.to_excel(writer, sheet_name='Total Spaces Summary', index=False)
        

    # Have to save the model parameters
    prams_path1 = os.path.join(out_dir, 'free_spaces_ols_params.csv')
    prams_path2 = os.path.join(out_dir, 'paid_spaces_ols_params.csv')

    model_params1 = mod_lm_free.params.to_frame().reset_index()
    model_params1.columns = ['feature', 'parameter']
    model_params1.to_csv(prams_path1, index=False)

    model_params2 = mod_lm_paid.params.to_frame().reset_index()
    model_params2.columns = ['feature', 'parameter']
    model_params2.to_csv(prams_path2, index=False)
    #Shldn't intersection co-eff be -ve?

if __name__=="__main__":
    run_space_estimation()