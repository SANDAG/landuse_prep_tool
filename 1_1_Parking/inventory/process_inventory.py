import os
import pandas as pd
import geopandas as gpd
import yaml
import numpy as np
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
import alphashape
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering

config = 'T:/ABM/release_test/tools/landuse_prep_tool/1_1_Parking/inventory/settings_inventory.yaml'
# config = './settings_inventory.yaml'
with open(config, "r") as stream:
    try:
        settings = yaml.load(stream, Loader=yaml.FullLoader)
        
        print(stream)
    except yaml.YAMLError as exc:
        print("ERRRORRR")
        print(exc)

inputs = settings.get('inputs')        
raw_path = inputs.get("raw_parking_inventory")
lu_path = inputs.get("land_use")
geometry = inputs.get("geometry")
raw_parking_df = pd.read_csv(raw_path).set_index("mgra")
lu_df = pd.read_csv(lu_path).set_index("mgra")
if set(['hparkcost', 'dparkcost', 'mparkcost', 'parkarea']).issubset(set(lu_df.columns)):
    lu_df.drop(columns=['hparkcost', 'dparkcost', 'mparkcost', 'parkarea'], inplace=True)
    
if set(['exp_hourly', 'exp_daily', 'exp_monthly', 'parking_type', 'parking_spaces']).issubset(set(lu_df.columns)):
    lu_df.drop(columns=['exp_hourly', 'exp_daily', 'exp_monthly', 'parking_type', 'parking_spaces'], inplace=True)

print("Reading MGRA shapefile data")
path = geometry

mgra_gdf = gpd.read_file(path).set_index("MGRA")[
    ["TAZ", "geometry"]
] 

def parking_reduction(raw_parking_df):
        # Free parking spaces
        df = (
            raw_parking_df[
                [
                    "on_street_free_spaces",
                    "off_street_free_spaces",
                    "off_street_residential_spaces",
                ]
            ]
            .sum(axis=1)
            .to_frame("free_spaces")
        )

        # Paid parking spaces
        df["paid_spaces"] = raw_parking_df[
            ["on_street_paid_spaces", "off_street_paid_private_spaces"]
        ].sum(axis=1)

        # Total spaces
        df["spaces"] = df[["paid_spaces", "free_spaces"]].sum(axis=1)

        # Drop zones with zero spaces
        df = df[df.spaces > 0]

        # Hourly cost
        hourly_costs = pd.concat(
            [
                raw_parking_df[
                    [
                        "on_street_hourly_cost_during_business",
                        "on_street_hourly_cost_after_business",
                    ]
                ].max(axis=1),
                raw_parking_df[
                    [
                        "off_street_paid_public_hourly_cost_during_business",
                        "off_street_paid_public_hourly_cost_after_business",
                    ]
                ].max(axis=1),
                raw_parking_df[
                    [
                        "off_street_paid_private_hourly_cost_during_business",
                        "off_street_paid_private_hourly_cost_after_business",
                    ]
                ].max(axis=1),
            ],
            axis=1,
        )

        dummy = ~hourly_costs.isnull().values
        spaces = raw_parking_df[
            [
                "on_street_paid_spaces",
                "off_street_paid_public_spaces",
                "off_street_paid_private_spaces",
            ]
        ]
        # Average weighted hourly cost, skipping NAs
        df["hourly"] = (hourly_costs * spaces.values).sum(axis=1) / (
            spaces * dummy
        ).sum(axis=1)
        df["hourly"] = hourly_costs.mean(axis=1)

        # Daily costs
        daily_costs = raw_parking_df[
            ["off_street_paid_public_daily_cost", "off_street_paid_private_daily_cost"]
        ]
        dummy = ~daily_costs.isnull().values
        spaces = raw_parking_df[
            ["off_street_paid_public_spaces", "off_street_paid_private_spaces"]
        ]
        # Average weighted daily cost, skipping NAs
        df["daily"] = (daily_costs * spaces.values).sum(axis=1) / (spaces * dummy).sum(
            axis=1
        )
        df["daily"] = daily_costs.mean(axis=1)

        # Monthly costs
        monthly_costs = raw_parking_df[
            [
                "off_street_paid_public_monthly_cost",
                "off_street_paid_private_monthly_cost",
            ]
        ]
        dummy = ~monthly_costs.isnull().values
        # Average weighted monthly cost, skipping NAs
        df["monthly"] = (monthly_costs * spaces.values).sum(axis=1) / (
            spaces * dummy
        ).sum(axis=1)
        df["monthly"] = monthly_costs.mean(axis=1)

        # Can't have $0 costs, replace with NA
        for cost in ["hourly", "daily", "monthly"]:
            df[cost] = df[cost].replace(0, np.NaN)

        return df

def MICE_imputation(reduced_df, lu_df):
    # Step 2: Imputation
    all(lu_df.acre == lu_df.effective_acres)
    model_df = reduced_df.copy()

    # Remove 999s
    model_df[model_df > 999] = None
    model_df = model_df.drop(
        columns=[x for x in model_df.columns if "imputed" in x]
    )

    # Define imputer
    # imputer = SimpleImputer(missing_values=np.nan, strategy='mean')
    imputer = IterativeImputer(random_state=100, max_iter=100, min_value=0)
    # imputer = KNNImputer(n_neighbors=5, weights='distance')
    imputer.fit(model_df)

    # Impute and format the results
    imputed_df = pd.DataFrame(
        data=imputer.transform(model_df),
        index=model_df.index,
        columns=model_df.columns,
    )
    imputed_df = imputed_df.rename(
        columns={k: k + "_imputed" for k in ["hourly", "daily", "monthly"]}
    )
    imputed_df = imputed_df[[x for x in imputed_df.columns if "imputed" in x]]

    return model_df.join(imputed_df)

def label_imputations(imputed_df, reduced_df):
    imputed_labels = pd.DataFrame(index=reduced_df.index)
    imputed_labels.loc[:, "imputed"] = False
    imputed_labels.loc[:, "imputed_types"] = ""
    imputed_labels.loc[:, "cost_types"] = ""
    cost_cols = ["hourly", "daily", "monthly"]

    for cost in cost_cols:
        imputed_labels.loc[reduced_df[cost].isnull(), "imputed"] = True
        imputed = imputed_labels.loc[reduced_df[cost].isnull(), "imputed_types"]
        not_imputed = imputed_labels.loc[~reduced_df[cost].isnull(), "cost_types"]
        imputed_labels.loc[reduced_df[cost].isnull(), "imputed_types"] += np.where(
            imputed == "", cost, " & " + cost
        )
        imputed_labels.loc[~reduced_df[cost].isnull(), "cost_types"] += np.where(
            not_imputed == "", cost, " & " + cost
        )

    imputed_labels.loc[
        imputed_labels.imputed.isnull(), "imputed_types"
    ] = "Not imputed"
    imputed_labels.loc[imputed_labels.cost_types == "", "cost_types"] = "None"
    imputed_df = imputed_df.join(imputed_labels)

    return imputed_df

def create_districts(combined_df):

    out_dir = settings.get("output_dir")
         
    print("Creating parking districts")
    districts_dict = parking_districts(
        imputed_parking_df, mgra_gdf, settings.get("walk_dist")
    )
    
    districts_df = districts_dict['districts'].drop(columns=['geometry'])        
    
    districts_df.to_csv(os.path.join(out_dir, 'districts.csv'))
    combined_df = combined_df.join(districts_df)
    return combined_df


def parking_districts(imputed_df, mgra_gdf, max_dist):
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

    return output


def write_output(combined_df):
    out_dir = settings.get("output_dir")
    combined_df.to_csv(os.path.join(out_dir, 'combined_parking.csv'))

print("Reducing raw parking data")
reduced_parking_df = parking_reduction(raw_parking_df)
# combined_df = lu_df.join(reduced_parking_df)

# Impute missing costs
imputed_parking_df = MICE_imputation(reduced_parking_df, lu_df)
imputed_parking_df = label_imputations(imputed_parking_df, reduced_parking_df)
combined_df = lu_df.join(imputed_parking_df)

combined_df = create_districts(combined_df)

write_output(combined_df)