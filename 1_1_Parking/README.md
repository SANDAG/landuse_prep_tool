# Parking Data Preparation for MGRA Land Use File (ABM3)
These scripts prepare expected parking cost data for SANDAG MGRA series 15 zones for base and future years. 

The processing includes the following steps organized into separate python modules:
- 1_inventory_preprocess: Reduces and imputes the parking inventory file (data collected in year 2022)
- 2_spaces_estimation: Estimates linear regressions models to predict free and paid spaces
- 3_costs_estimation: Applies regression models to estimate paid and free spaces, creates parking districts, and calculates expected costs

# Steps & Analysis

## 1. Reduction and Imputing Raw Parking Inventory Data

### Input
    - mgra_parking_inventory.csv

### Output
    - imputed_parking_costs.csv

- Weighted average cost of private and public parking, assuming weight is n-spaces $= \frac{(n_{private} * cost_{private} + n_{public} * cost_{public})}{n_{private} + n_{public}}$
- Sum of public and private spaces
- Max cost for business hours or after hours

### Assumptions
- Collapse on-street/off-street segment
  - assuming all on-street are "public"
  - assume that off-street residential are "free" 
  - assume that public space counts are inclusive of private space count
- Reduce business hours and after hours by selecting the max value
  - assume peak pricing is most critical in daily pricing
  - assume there are no $0 costs in inventory, otherwise they would be considered free spaces or NaN
  - assume max daily on-street period is 10 hours

## 2. Creation of Space Estimation Model

### Input
    - imputed_parking_costs.csv
    - 2022 Landuse file
    - MGRA 15 Shapefile
    - SANDAG Bike Networks
    - SANDAG Bike Nodes

### Output
    - Aggregated Street data
    - Model parameters for free & paid spaces

- Uses Sandag bike network to get the length and intersection count excluding the highways, bike only paths and private roads.
- Find the intersection of the network with MGRAs spatial join and aggregate.
- Uses Landuse 2022 file to get the household and employees data for each MGRA.
- Linear model is fitted with the following predictors for both free and paid spaces.
    - formula_free = "free_spaces ~ 0 + length + intcount + hh_sf + hh_mf + emp_total"
    - formula_paid = "paid_spaces ~ 0 + length + intcount + acres + hh_sf + emp_total"

Note: First 2 steps are static and needs to be calculated only for 2022 Landuse file for each version

## 3. Space Estimation, District Creation and Cost Estimation
This file is called by ../2_ABM_Preprocess/run_preprocess.py

### Input
    - imputed_parking_costs.csv
    - Landuse file (for any year)
    - MGRA 15 Shapefile
    - Aggregated Street data (currently uses 2022 network)
    - Model parameters for free & paid spaces
    - Parking Policy (Optional)
    - Policy Type (Optional)
    - Policy Rate (Optional)

### Output
    - Parking Dataframe with estimated costs, parking spaces and parking type

### Space Estimation
- Both paid and free spaces are estimated with Any(2022 or future) Landuse file, street data and imputed_parking_df using dot product.
- Imputed parking data is updated with new paid spaces where hourly costs greater than 0 and paid spaces are missing.

### District Creation
- Districts are created with filter on paid spaces MGRAs:
    Three step process:
    1. Spatially cluster zones with paid parking based on a maximum distance threshold
    2. Create a concave hull for each cluster plus a walking distance buffer around hull
    3. Join all zones within that hull

#### Clustering
Spatial clustering uses a "Agglomerative Clustering" technique where points are grouped into discrete clusters based on distance.

Minimum distance between the MGRAS are considered. The zones with parking costs can then be grouped together based on the maximum walking distance threshold.

#### Concave Hull
A convex hull is formed from as the minimum shape that included all points. However, a convex hull is not sensitive to concave or "gerrymandered" shapes. To form a concave shape, the "alpha shape" can be formed using a Delaunay triangulation technique. 

#### Spatial Join
Once the concave hull is found for each parking cluster, a simple buffer distance equal to the maximum walking distance is added to buffer around the zone to include additional walkable zones. Using the buffered concave hulls, all MGRA zones are spatially joined if they are within the concave hull envelope, forming discrete "paid parking districts".

Note:<br>
parking_type:
- Parking Type 1: parking constrained area: has cluster_id AND district_id
- Parking Type 2: buffer around parking constrained area which is used to include free spaces to average into parking cost calculation: has district_id but no cluster_id
- Parking Type 3: no parking cost: Has neither cluster_id nor district_id
    
### Cost Estimation

- Cost_df creation with district data with parking type 1 & 2 MGRAs
- Joined with estimated paid, free spaces and imputed parking data.
- Spaces for cost estimation or "cost_spaces" calculated with following conditions:
    - if parking_type=1 & paid_spaces>0 then paid_spaces (from 2022 parking inventory)
    - if parking_type=1 & paid_spaces<=0 then estimated_paid_spaces (from regression model)
    - if parking_type=2 & free_spaces>0 then free_spaces (from 2022 parking inventory)
    - if parking_type=2 & free_spaces<=0 then estimated_free_spaces (from regression model)
    - if is_noprkspace(zone within parking district but has no parking spaces) True then cost_spaces=0

- Distance matrix is calculated for zones within parking district and distance between MGRA less than Maximum walking distance defined.
- Expected costs is calculated by below formula:
    - $numerator_i = e^{dist * \beta_{walk}} * cost_spaces * cost$
    - $denominator_i = e^{dist * \beta_{walk}} * cost_spaces$

Expected parking cost = $\frac{\sum numerator_i}{\sum denominator_i}$

