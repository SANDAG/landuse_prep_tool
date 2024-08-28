# SANDAG ABM3 Land Use Preparation Tool
Tool for processing outputs given to us from Estimates and Forecasts to be used in ABM3. There are three main parts of the tool:
1. Process outputs of the 2022 parking inventory to impute missing data.
2. Estimate regression models to predict the number of free and paid spaces in an MGRA.
3. Create household, person, and land use inputs for running ABM.

Unless there are changes to the base year network or inventory, only the third step needs to be run.

A dictionary of the settings in config.yaml can be found [here](settings_dictionary.md).

## To easily run without parking preprocessing
1. Gain access to the database RP2025 on the server DGISWSQL22 from GIS.
2. Create a directory to run in.
3. Clone the repo into the directory.
4. Create anaconda environment using the environment.yml file.
5. Open up config_[YEAR].yaml and set `run_ABM_preprocess` to be `True`.
6. If no parking policy is being applied, set `implement_policy` to be `False`.
7. Edit the setting `EF_dir` and `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
8. Edit the `output_dir` to the desired output location.
9. Update the name of config file with scenario year.
10. Open Anaconda prompt, navigate into the cloned repo and activate the environment and run run_lanuse_preprocessing.bat. The files will be created in the specified `output_dir`

## To easily run parking preprocessing
1. Create a directory to run in and clone the repo into the directory. Create folders in the clone called "parking_processed" and "parking_inputs"
2. Copy the the files auxiliary_columns.csv and micro_mobility_allyears.csv from T:\ABM\data\sr15_inputs\landuse_prep into the directory.
3. Copy the file 'mgra_parking_inventory.csv' from T:\ABM\data\sr15_inputs\landuse_prep\parking_inputs into the parking_inputs folder ("old" folder not needed).
4. Copy ParkingPolicies_[YEAR].csv from T:\ABM\data\sr15_inputs\landuse_prep\parking_outputs into the _processed folder.
5. Open up config_procpkg.yaml and set `run_parking_inventory_preprocess` and 'run_parking_space_estimation' to be `True` .
6. Edit the setting `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
7. Edit the setting `bike_net` and 'bike_node' to be the directory with the latest active transportation network.
8. Open Anaconda prompt, navigate into the cloned repo and create an Anaconda environment using the environment.yml file.
9. Activate the environment and run run_parking_preprocessing.bat. The files will be created in the specified `parking_output_dir` 
