import numpy as np
import pandas as pd
import os
import geopandas as gpd
import yaml
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
import sys

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
    df["total_spaces"] = df[["paid_spaces", "free_spaces"]].sum(axis=1)

    # Drop zones with zero spaces
    df = df[df.total_spaces > 0]

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
    spaces_df = raw_parking_df[
        [
            "on_street_paid_spaces",
            "off_street_paid_public_spaces",
            "off_street_paid_private_spaces",
        ]
    ]
    # Average weighted hourly cost, skipping NAs
    df["hourly"] = (hourly_costs * spaces_df.values).sum(axis=1) / (
        spaces_df * dummy
    ).sum(axis=1)
    df["hourly"] = hourly_costs.mean(axis=1)

    # Daily costs
    daily_costs = raw_parking_df[
        ["off_street_paid_public_daily_cost", "off_street_paid_private_daily_cost"]
    ]
    dummy = ~daily_costs.isnull().values
    spaces_df = raw_parking_df[
        ["off_street_paid_public_spaces", "off_street_paid_private_spaces"]
    ]
    # Average weighted daily cost, skipping NAs
    df["daily"] = (daily_costs * spaces_df.values).sum(axis=1) / (spaces_df * dummy).sum(
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
    df["monthly"] = (monthly_costs * spaces_df.values).sum(axis=1) / (
        spaces_df * dummy
    ).sum(axis=1)
    df["monthly"] = monthly_costs.mean(axis=1)

    # Can't have $0 costs, replace with NA
    for cost in ["hourly", "daily", "monthly"]:
        df[cost] = df[cost].replace(0, np.NaN)

    return df

def MICE_imputation(reduced_df):
    # Step 2: Imputation
    model_df = reduced_df[['paid_spaces','free_spaces',"hourly", "daily", "monthly"]].copy()

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

def write_output(combined_df):
    out_dir = settings.get("parking_output_dir")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    combined_df.to_csv(os.path.join(out_dir, 'imputed_parking_costs.csv'))

if __name__ == "__main__":
    
    config = sys.argv[1]
    with open(config, "r") as stream:
        try:
            settings = yaml.load(stream, Loader=yaml.FullLoader)
            
            print(stream)
        except yaml.YAMLError as exc:
            print("ERRRORRR")
            print(exc)

    inputs = settings.get('inputs')        
    raw_path = inputs.get("raw_parking_inventory")
    raw_parking_df = pd.read_csv(raw_path).set_index("mgra")
    print("Reducing raw parking data")
    
    reduced_parking_df = parking_reduction(raw_parking_df)

    # Impute missing costs
    imputed_parking_df = MICE_imputation(reduced_parking_df)
    imputed_parking_df = label_imputations(imputed_parking_df, reduced_parking_df)
    imputed_parking_df['total_spaces'] = imputed_parking_df['paid_spaces'] + imputed_parking_df['free_spaces']
    imputed_parking_df[['hourly_imputed','daily_imputed','monthly_imputed']] = imputed_parking_df[['hourly_imputed','daily_imputed','monthly_imputed']].round(3)
    imputed_parking_df.loc[ imputed_parking_df['paid_spaces']<=0,['hourly_imputed','daily_imputed','monthly_imputed']]=0
    write_output(imputed_parking_df)