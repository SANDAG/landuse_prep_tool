# SANDAG ABM3 Land Use Preparation Tool
Tool for processing outputs given to us from Estimates and Forecasts to be used in ABM3

A dictionary of the settings in config.yaml can be found [here](settings_dictionary.md).

## To easily run tool
1. Gain access to the database RP2025 on the server DGISWSQL22 from GIS.
2. Create a directory to run in. Create folders called "parking_inputs" and "parking_outputs."
3. Copy the the files auxiliary.csv and micro_mobility.csv from T:\ABM\data\sr15_inputs\landuse_prep into the directory.
4. Copy the contents of T:\ABM\data\sr15_inputs\landuse_prep\parking_inputs into the parking_inputs folder ("old" folder not needed).
5. Copy ParkingPolicies_[YEAR].csv from T:\ABM\data\sr15_inputs\landuse_prep\parking_outputs into the parking_outputs folder.
6. Clone the repo into the directory.
7. Open up config.yaml and do a find and replace searching for "T:\ABM\data\sr15_inputs\landuse_prep" and replacing them with the directory you created.
8. Within config.yaml, update `scenario_year` and `ff_year` to be the year of the scenario that you're preparing the land use for.
9. Edit the setting `EF_dir` and `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
10. Open, Anaconda prompt, navigate into the cloned repo and create an Anaconda environment using the environment.yml file.
11. Activate the environment and run run_landuse_preprocessing.bat. The files will be created in the specified output_dir (the clone of the repo if that is unchanged).
