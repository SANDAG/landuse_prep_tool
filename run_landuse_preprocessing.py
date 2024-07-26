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
        os.system(
            r"conda activate {0} && python 1_1_Parking\1_inventory_preprocess\1_parking_preprocess.py {1}".format(
                env_name,
                config_file
            )
        )
        print("preprocessed inventory files are written")

    if settings["run_parking_spaces_estimation"]:
        os.system(
            r"conda activate {0} && python 1_1_Parking\2_spaces_estimation\2_parking_spaces.py {1}".format(
                env_name,
                config_file
            )
        )
        print("Initial files are written")
        
    if settings["run_ABM_preprocess"]:
        os.system(
            r"conda activate {0} && python 2_ABM_Preprocess\run_preprocess.py {1}".format(
                env_name,
                config_file
            )
        )
        print("basic files are written")