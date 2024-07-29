# SANDAG ABM3 Land Use Preparation Tool
Tool for processing outputs given to us from Estimates and Forecasts to be used in ABM3

## To easily run tool
1. Create a directory to run in. Create folders called "parking_inputs" and "parking_outputs."
2. Copy the contents of T:\ABM\data\sr15_inputs\landuse_prep into the directory.
3. Copy the contents of T:\ABM\data\sr15_inputs\landuse_prep\parking_inputs into the parking_inputs folder.
4. Clone the repo into the directory.
6. Open up config.yaml and do a find and replace searching for "T:\ABM\data\sr15_inputs\landuse_prep" and replacing them with the directory you created.
7. Open, Anaconda prompt, navigate into the cloned repo and create an Anaconda environment using the environment.yml file.
8. Activate the environment and run run_landuse_preprocessing.bat. The files will be created in the specified output_dir (the clone of the repo if that is unchanged).