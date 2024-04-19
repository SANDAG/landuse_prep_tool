import os
import folium
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import yaml
import os
from sklearn.cluster import AgglomerativeClustering
import alphashape

def create_districts(imputed_df, mgra_gdf, max_dist):
    # 1. Spatially cluster zones with paid parking
    paid_zones = mgra_gdf.loc[
        imputed_df[imputed_df.paid_spaces > 0].index, ["TAZ", "geometry"]
    ]
    
    # Calculate similarity matrix of ever zone to zone pair on their geometries not centroid
    print("Calculating similarity matrix")
    data_matrix = np.zeros([len(paid_zones)] * 2)
    for i, z in enumerate(tqdm(paid_zones.index)):
        data_matrix[i, :] = (
            paid_zones.geometry.distance(paid_zones.loc[z].geometry) / 5280
        )

    # Run clustering model -- kind of excessive but whatever
    print("Clustering zones")
    model = AgglomerativeClustering(
        metric="precomputed",
        compute_full_tree=True,
        linkage="single",
        distance_threshold=max_dist,
        n_clusters=None,
    ).fit(data_matrix)

    # Create cluster label dataframe to join from
    parking_clusters_labels = pd.DataFrame(
        model.labels_, columns=["cluster_id"], index=paid_zones.index
    )
    parking_clusters = paid_zones.join(parking_clusters_labels)

    # 2. Create a concave hull for each cluster & add buffer
    print("Creating concave hulls")

    def concave_hull(geo):
        alpha = 2.5 / (max_dist * 5280)
        flat_coords = [xy for geo in geo.exterior for xy in geo.coords]
        return alphashape.alphashape(flat_coords, alpha)

    hull_geoms = (
        parking_clusters.groupby("cluster_id")
        .geometry.apply(concave_hull)
        .set_crs(mgra_gdf.crs.to_epsg())
        .to_frame("geometry")
    )
    hull_geoms.index.name = "hull_id"
    buffer_geoms = hull_geoms.geometry.buffer(max_dist * 5280).to_frame("geometry")

    # Consolidate overlapping geometries
    parents = {}
    for i, geom in enumerate(buffer_geoms.geometry):
        connected = geom.intersects(buffer_geoms.geometry)
        edges = buffer_geoms.index[connected].to_list()
        for x in edges:
            if x not in parents:
                parents[x] = i

    district_ids = pd.DataFrame.from_dict(
        parents, orient="index", columns=["district_id"]
    )
    buffer_geoms = buffer_geoms.join(district_ids).dissolve("district_id")

    # 3. Spatial Join all zones within hulls
    print("Performing spatial joins")
    # Add cluster id
    parking_districts = mgra_gdf[["geometry"]].join(
        parking_clusters[["cluster_id"]]
    )

    # Add hull id
    parking_districts = parking_districts.sjoin(
        hull_geoms.geometry.reset_index(), how="left", predicate="within"
    ).drop(columns="index_right")

    # Add district
    parking_districts = parking_districts.sjoin(
        buffer_geoms.geometry.reset_index(), how="left", predicate="within"
    ).drop(columns="index_right")

    # Determine parking_zone_type
    # is_prkdistrict    = zone within parking district
    # is_noprkspace     = zone within parking district but has no parking spaces

    # filters
    is_district = ~parking_districts.district_id.isnull()
    is_nodata = ~parking_districts.index.isin(paid_zones.index)
    is_hull = ~parking_districts.hull_id.isnull()

    # Assign
    parking_districts["is_prkdistrict"] = False
    parking_districts["is_noprkspace"] = False
    parking_districts.loc[is_district, "is_prkdistrict"] = True
    parking_districts.loc[is_hull & is_nodata, "is_noprkspace"] = True
    
    # parking_type:
    # 1: parking constrained area: has cluster_id AND district_id
    # 2: buffer around parking constrained area which is used to include free spaces to average into parking cost calculation: has district_id but no cluster_id
    # 3: no parking cost: Has neither cluster_id nor district_id
    
    parking_districts['parking_type'] = None
    parking_districts.loc[~parking_districts.cluster_id.isnull() & ~parking_districts.district_id.isnull(), "parking_type"] = 1
    parking_districts.loc[parking_districts.cluster_id.isnull() & ~parking_districts.district_id.isnull(), "parking_type"] = 2
    parking_districts['parking_type'] = parking_districts['parking_type'].fillna(3)
            
    output = {
        "districts": parking_districts,
        "hulls": hull_geoms,
        "buffered_hulls": buffer_geoms,
        "clusters": parking_clusters,
    }

    districts_df = output['districts'].drop(columns=['geometry'])        
    # districts_df.to_csv(os.path.join(out_dir, 'districts.csv'))
    return districts_df

def estimate_spaces_df(street_data,model_params,method='lm'):
    #Linear model prediction
    if method == "lm":
        temp_spaces = street_data.dot(model_params.set_index('feature')['parameter']).clip(0)
        #dot product of model co-eff with respective columns
    else:
        temp_spaces = calculate_spaces(
            street_data.length, street_data.intcount
        ).astype(int)

    return temp_spaces

def calculate_spaces(length, intcount):
    return 2 * (length / 10) - 2 * intcount

#depends only on mgra - calculates distances between mgra
def pre_calc_dist(geos, max_dist):
    dist_matrix = np.zeros([len(geos.index)] * 2)
    for i, zone in enumerate(tqdm(geos.index)):
        dist_matrix[i, :] = geos.distance(geos.loc[zone]) / 5280
    dist_df = pd.DataFrame(dist_matrix, index=geos.index, columns=geos.index)
    dist_df.index.name = "OZONE"
    dist_df = dist_df.reset_index().melt(
        id_vars="OZONE", var_name="DZONE", value_name="dist"
    )
    dist_df = dist_df[dist_df.dist <= max_dist]
    dist_df = dist_df.reset_index()

    dist_df = dist_df.set_index("DZONE")

    return dist_df

def expected_parking_cost(dest_id,costs_df,dist_df,walk_coef,cost_type=["hourly", "daily", "monthly"]):
    # If dest_id not in parking costs at all, default to 0
    if dest_id in costs_df.index:
        # If no other zone within walking distance, default to parking cost of zone
        if dest_id in dist_df.index:
            # Find all zones within walking distance
            dest_df = dist_df.loc[dest_id]

            # Swap the indices and join costs to the aternative zones to be averaged
            dest_df = dest_df.reset_index().set_index("OZONE").join(costs_df)

            # Natural exponent -- compute once
            expo = np.exp(dest_df.dist.values * walk_coef) * dest_df.cost_spaces.values

            # numerator = sum(e^{dist * \beta_{dist}} * spaces * cost)
            # denominator = sum(e^{dist * \beta_{dist}} * spaces)
            numer = np.nansum(expo * dest_df[cost_type].values.T, axis=1)
            denom = np.nansum(expo)
        
            if denom > 0:
                expected_cost = dict(zip(cost_type, numer / denom))
            else:
                expected_cost = {x: 0 for x in cost_type}

        else:
            expected_cost = costs_df.loc[dest_id, cost_type].to_dict()

    else:
        expected_cost = {x: 0 for x in cost_type}

    expected_cost["index"] = dest_id
    
    return expected_cost

def run_expected_parking_cost(max_dist,walk_coef,districts_df,mgra_gdf,costs_df):
    district_ids = districts_df[districts_df.is_prkdistrict].index.unique()
    geos = mgra_gdf.loc[district_ids].geometry
    # costs_df = prepare_cost_table(imputed_parking_df, estimated_space_df, districts_df)
    print("pre-calculate walk distance matrix")
    dist_df = pre_calc_dist(geos, max_dist)
    # Calculate expected cost for all zones in districts, all else are 0 cost

    exp_prkcosts = [
            expected_parking_cost(x, costs_df, dist_df, walk_coef)
            for x in tqdm(geos.index)
        ]
    
    exp_prkcosts_df = pd.DataFrame(exp_prkcosts).set_index("index")
    # print(exp_prkcosts_df.columns)
    exp_prkcosts_df = exp_prkcosts_df.rename(
        columns={x: "exp_" + x for x in exp_prkcosts_df.columns}
    )
    exp_prkcosts_df = exp_prkcosts_df.reindex(mgra_gdf.index)
    exp_prkcosts_df = exp_prkcosts_df.fillna(0)
    return exp_prkcosts_df.round(3)
