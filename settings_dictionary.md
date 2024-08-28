**config_procpkg.yaml**

**run_parking_inventory_preprocess:** Switch to run the preprocessing of the parking inventory data.

**run_parking_spaces_estimation:** Switch to estimate the number of parking spaces per MGRA.

**raw_parking_inventory:** Input file 'mgra_parking_inventory.csv' for the raw parking inventory.

**base_lu:** The base year land use to use for estimating the regression parameters for the number of free and paid spaces.

**bike_net:** Shapefile with the links of the active transportation network.

**bike_node:** Shapefile with the nodes of the active transportation network.

**geometry_file:** Shapefile containing the MGRA polygons.

**parking_output_dir:** The directory to write the outputs of the parking inventory preprocessing and parking spaces estimation in. **The parking outputs will be written in this location.**

**config_year.yaml**

**run_ABM_preprocess:** Switch to run full ABM land use preprocessing.

**parking_output_dir:** The directory containing the outputs of the parking preprocessing steps (parking inventory preprocess and parking space estimation). **These files are used as input of ABM preprocessing step.**

**geometry_file:** Shapefile containing the MGRA polygons.

**input_dir:** Directory containing the inputs for the ABM preprocessing.

**EF_dir:** Directory containing the files provided by Estimates and Forecasts. 

**output_dir:** The directory to write the outputs of the ABM preprocessing in. **The ABM inputs will be written in this location.**

**scenario_year:** The year of the scenario to prepare the inputs for.

**ff_year:** The year of the flexible fleet network to use. If not provided it will use the same value as `scenario_year`. This only is needed if preparing inputs for a no-build scenario, in which case it should be set to the base year (2022).

**household_file:** The name of the household file provieded by E&F. It should be within `EF_dir`.

**persons_file:** The name of the person file provieded by E&F. It should be within `EF_dir`.

**landuse_file:** The name of the land use file provieded by E&F. It should be within `EF_dir`.

**auxiliary_file:** File to be merged with the MGRA file. Contains the elementary and high school districts, availability of remote AV parking, as well as the number of refueling stations for each MGRA. This file needs to be present in `input_dir`.

**micro_mob_file:** Contains the micromobility access times for each mobility hub type. This is joined to the MGRA file based on the mobility hub type of the MGRA if the MGRA is within a mobility hub. This file needs to be present in `input_dir`.

**walk_dist:** The maximum walking distance used in parking cost estimation.

**walk_coef:** Coefficient for walk distance when estimating parking costs.

**max_est_paid_spaces:** The maximum number of paid spaces in an MGRA if `policy_type == "mohubs"`.

**max_est_free_spaces:** The maximum number of free spaces in an MGRA if `policy_type == "mohubs"`.

**imputed_parking_df:** The file containing imputed parking data. This is the output of the parking inventory preprocess step.

**street_file:**: File containing the street data per MGRA. Created during parking space estimation.

**model_params_free:**: File containing regression parameters to estimate the number of free spaces in each MGRA.

**model_params_paid:**: File containing regression parameters to estimate the number of paid spaces in each MGRA.

**implement_policy:** Boolean indicating whether or not to implement a parking policy.

**policy_type:** Indicates what policy type to use. Must be either `pca` for PCA MGRAs, or `mohubs` for all mobility hubs.

**parking_policy:** File containing the prices that define the policy.

**update_rate:** Rate to update parking rates. Must be 0.5, 1, or 1.5.

**server:** GIS server containing information for different years.

**database:** Database on `server` containing the desired information.
