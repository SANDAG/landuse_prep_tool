import os
import sys
import yaml

if __name__ == "__main__":

    config_file = sys.argv[1]
    with open(config_file, "r") as f:
        settings = yaml.safe_load(f)
        f.close()

    env_name = os.environ["CONDA_DEFAULT_ENV"]

    if settings["run_parking_inventory_preprocess"]:
        errorcode = os.system(
            r"conda activate {0} && python T:\ABM\release_test\tools\landuse_prep_tool\version_2_0\1_1_Parking\1_inventory_preprocess\1_parking_preprocess.py {1}".format(
                env_name,
                config_file
            )
        )
        if errorcode == 0:
            print("preprocessed inventory files are written")
        else:
            raise Exception("Error in process")

    if settings["run_parking_spaces_estimation"]:
        errorcode = os.system(
            r"conda activate {0} && python T:\ABM\release_test\tools\landuse_prep_tool\version_2_0\1_1_Parking\2_spaces_estimation\2_parking_spaces.py {1}".format(
                env_name,
                config_file
            )
        )
        if errorcode == 0:
            print("Initial files are written")
        else:
            raise Exception("Error in process")