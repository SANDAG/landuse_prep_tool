### Script to preprocess the parking inventory file to prepare for Landuse Preprocess script

#### Ways to run the parking script:
1. 
 - If the inventory file changes run the "1_1_Parking\1_inventory_preprocess"
 - If the Sandag Bike network or mgra15 geometry changes, run "1_1_Parking\2_spaces_estimation" to get the spaces estimation model parameters

2. 
 - We can introduce new costs for mgra in imputed_parking_costs.csv file. (optional)
 - Run the preprocessor directly which will use the "1_1_Parking\3_costs_estimation" to calculate the parking cost df
 
