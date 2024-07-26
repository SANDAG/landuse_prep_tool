import os
import sys
import yaml

config_file = sys.argv[1]
with open(config_file, "r") as f:
    settings = yaml.safe_load(f)
    f.close()

if settings["run_parking_inventory_preprocess"]:
    os.system(r"1_1_Parking\1_inventory_preprocess\1_parking_preprocess.py " + config_file)
    print("preprocessed inventory files are written")
if settings["run_parking_spaces_estimation"]:
    os.system(r"1_1_Parking\2_spaces_estimation\2_parking_spaces.py " + config_file)
    print("Initial files are written")
if settings["run_ABM_preprocess"]:
    os.system(r"2_ABM_Preprocess\run_preprocess.py " + config_file)
    print("basic files are written")