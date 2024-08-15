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
4. Open up config.yaml and set `run_parking_inventory_preprocess` and `run_parking_spaces_estimation` to be `False`.
5. If no parking policy is being applied, set `implement_policy` to be `False`.
6. Edit the setting `EF_dir` and `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
7. Edit the `output_dir` to the desired output location.
8. Open Anaconda prompt, navigate into the cloned repo and create an AnActivate the environment and run run_landuse_preprocessing.bat. The files will be created in the specified `output_dir` (the clone of the repo if that is unchanged).aconda environment using the environment.yml file.

## To easily run all steps
1. Gain access to the database RP2025 on the server DGISWSQL22 from GIS.
2. Create a directory to run in and clone the repo into the directory. Create folders in the clone called "parking_inputs" and "parking_outputs."
3. Copy the the files auxiliary.csv and micro_mobility.csv from T:\ABM\data\sr15_inputs\landuse_prep into the directory.
4. Copy the contents of T:\ABM\data\sr15_inputs\landuse_prep\parking_inputs into the parking_inputs folder ("old" folder not needed).
5. Copy ParkingPolicies_[YEAR].csv from T:\ABM\data\sr15_inputs\landuse_prep\parking_outputs into the parking_outputs folder.
6. Open up config.yaml and do a find and replace searching for "T:\ABM\data\sr15_inputs\landuse_prep" and replacing them with the directory you created.
7. Within config.yaml, update `scenario_year` and `ff_year` to be the year of the scenario that you're preparing the land use for.
8. Edit the setting `EF_dir` and `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
9. Open Anaconda prompt, navigate into the cloned repo and create an Anaconda environment using the environment.yml file.
10. Activate the environment and run run_landuse_preprocessing.bat. The files will be created in the specified `output_dir` (the clone of the repo if that is unchanged).
