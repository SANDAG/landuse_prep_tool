# Script to preprocess the parking inventory file to prepare for Landuse Preprocess script
This script prepares expected parking cost data for SANDAG MGRA series 15 zones. 

The processing includes the following steps organized into separate python modules:
- 1_inventory_preprocess: Reduces and imputes the parking inventory file
- 2_spaces_estimation: Creates the linear model parameters for space estimation
- 3_costs_estimation: Estimates spaces, finds parking district, calculates expected costs

# To prepare new parking costs:
1. Run the space estimation model with 2022 Landuse file to get model parameters
2. Run the main run_preprocess.py which will call the cost estimation for parking with new landuse and parking policy.



# Steps & Analysis

## 1. Reducing and Imputing raw parking inventory data

### Input
    - mgra_parking_inventory.csv

### Output
    - imputed_parking_costs.csv

- Weighted average cost of private and public parking, assuming weight is n-spaces $= \frac{(n_{private} * cost_{private} + n_{public} * cost_{public})}{n_{private} + n_{public}}$
- Sum of public and private spaces
- Max cost for business hours or after hours

### Some assumptions
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
This file is called by run_preprocess.py

### Input
    - imputed_parking_costs.csv
    - Landuse file
    - MGRA 15 Shapefile
    - Aggregated Street data
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

### Cost Estimation

- Cost_df creation with district data on is_prkdistrict filter = zone within parking district
- Joined with estimated paid, free spaces and imputed parking data.
- cost_spaces calculated with following condition:
    - if parking_type=1 & paid_spaces>0 then paid_spaces
    - if parking_type=1 & paid_spaces<=0 then estimated_paid_spaces
    - if parking_type=2 & free_spaces>0 then free_spaces
    - if parking_type=2 & free_spaces<=0 then estimated_free_spaces
    - if is_noprkspace(zone within parking district but has no parking spaces) True then cost_spaces=0

- Distance matrix is calculated for zones within parking district and distance between MGRA less than Maximum walking distance defined.
- Expected costs is calculated by below formula:
    - $numerator_i = e^{dist * \beta_{walk}} * cost_spaces * cost$
    - $denominator_i = e^{dist * \beta_{walk}} * cost_spaces$

Expected parking cost = $\frac{\sum numerator_i}{\sum denominator_i}$


Note:<br>
parking_type:
    1: parking constrained area: has cluster_id AND district_id
    2: buffer around parking constrained area which is used to include free spaces to average into parking cost calculation: has district_id but no cluster_id
    3: no parking cost: Has neither cluster_id nor district_id
