import os
import sys
import yaml

if __name__ == "__main__":

    config_file = sys.argv[1]
    with open(config_file, "r") as f:
        settings = yaml.safe_load(f)
        f.close()

    env_name = os.environ["CONDA_DEFAULT_ENV"]

    if settings["run_ABM_preprocess"]:
        errorcode = os.system(
            r"conda activate {0} && python T:\ABM\release_test\tools\landuse_prep_tool\version_2_0\2_ABM_Preprocess\run_preprocess.py {1}".format(
                env_name,
                config_file
            )
        )
        if errorcode == 0:
            print("basic files are written")
        else:
            raise Exception("Error in process")