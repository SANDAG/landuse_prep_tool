import subprocess
import sys
import yaml

if __name__ == "__main__":

    config_file = sys.argv[1]
    with open(config_file, "r") as f:
        settings = yaml.safe_load(f)
        f.close()

    if settings["run_parking_inventory_preprocess"]:
        script = r"T:\ABM\release_test\tools\landuse_prep_tool\version_2_0\1_1_Parking\1_inventory_preprocess\1_parking_preprocess.py"
        errorcode = subprocess.call([sys.executable, str(script), config_file])
        if errorcode == 0:
            print("preprocessed inventory files are written")
        else:
            raise Exception("Error in process")

    if settings["run_parking_spaces_estimation"]:
        script = r"T:\ABM\release_test\tools\landuse_prep_tool\version_2_0\1_1_Parking\2_spaces_estimation\2_parking_spaces.py"
        errorcode = subprocess.call([sys.executable, str(script), config_file])
        if errorcode == 0:
            print("Initial files are written")
        else:
            raise Exception("Error in process")