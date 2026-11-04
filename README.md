# SANDAG ABM3 Land Use Preparation Tool
Tool for preparing land use and parking inputs for ABM3 from Estimates and Forecasts outputs. Household and person processing is handled by the [Population-Sim pipeline](https://github.com/SANDAG/Population-Sim/pull/117). There are three main parts of the tool:
1. Process outputs of the 2022 parking inventory to impute missing data.
2. Estimate regression models to predict the number of free and paid spaces in an MGRA.
3. Create land use inputs for running ABM.

Unless there are changes to the base year network or inventory, only the third step needs to be run.

A dictionary of the settings in config.yaml can be found [here](settings_dictionary.md).

## Python environment with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on Windows from PowerShell:

```powershell
winget install --id astral-sh.uv -e
```

Open a new terminal, navigate to the cloned repository, and create the environment:

```powershell
uv sync
```

uv downloads Python 3.11 if needed and installs the project dependencies into `.venv`.
No environment activation is required. In VS Code, use
**Python: Select Interpreter** to select `.venv\Scripts\python.exe`.
Dependencies are defined in `pyproject.toml`; `uv.lock` records the resolved versions.
The geospatial dependencies use Shapely 1.x-compatible versions because
`geonetworkx` relies on APIs removed in Shapely 2. NumPy is kept below 2 for
compatibility with that stack.

Run either workflow from the repository root (replace the config name as needed):

```powershell
uv run python run_landuse_preprocessing.py config_year.yaml
uv run python run_parking_preprocessing.py config_procpkg.yaml
```

The batch files also use uv and retain their fixed shared-drive script paths.
Before running the land use batch file, replace `config_{year}.yaml` in its
command with your config filename. The parking batch file uses `config_procpkg.yaml`.
To choose a config without editing a batch file, use the Python commands above.

Database access still requires the appropriate SQL Server ODBC driver installed on
Windows, database permissions, and access to any configured network drives. uv
installs `pyodbc`, not the system ODBC driver.

## To easily run without parking preprocessing
1. Gain access to the database RP2025 on the server DGISWSQL22 from GIS.
2. Create a directory to run in.
3. Clone the repo into the directory.
4. Create the Python environment with `uv sync` (see above).
5. Open up config_[YEAR].yaml and set `run_ABM_preprocess` to be `True`.
6. If no parking policy is being applied, set `implement_policy` to be `False`.
7. Edit the setting `EF_dir` and `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
8. Edit the `output_dir` to the desired output location.
9. Update the name of config file with scenario year.
10. Open PowerShell, navigate into the cloned repo and run `uv run python run_landuse_preprocessing.py config_[YEAR].yaml` using your renamed config file. The files will be created in the specified `output_dir`.

## To easily run parking preprocessing
1. Create a directory to run in and clone the repo into the directory. Create folders in the clone called "parking_processed" and "parking_inputs"
2. Copy the the files auxiliary_columns.csv and micro_mobility_allyears.csv from T:\ABM\data\sr15_inputs\landuse_prep into the directory.
3. Copy the file 'mgra_parking_inventory.csv' from T:\ABM\data\sr15_inputs\landuse_prep\parking_inputs into the parking_inputs folder ("old" folder not needed).
4. Copy ParkingPolicies_[YEAR].csv from T:\ABM\data\sr15_inputs\landuse_prep\parking_outputs into the _processed folder.
5. Open up config_procpkg.yaml and set `run_parking_inventory_preprocess` and 'run_parking_space_estimation' to be `True` .
6. Edit the setting `base_lu` to be the directory with the outputs from Estimates and Forecasts that the land use prep tool will process.
7. Edit the setting `bike_net` and 'bike_node' to be the directory with the latest active transportation network.
8. Open PowerShell, navigate into the cloned repo and create the Python environment with `uv sync`.
9. Run `.\run_parking_preprocessing.bat`. The files will be created in the specified `parking_output_dir`.

## To read PopulationSim outputs from Databricks

1. secrets.yml

Copy `secrets.example.yml` to `secrets.yml` and fill in the workspace URL, SQL warehouse id, catalog and schema. This file is included in the `.gitignore` to keep it private. 
```yaml
databricks:
  host: "<workspace-url>" # Databricks workspace URL
  warehouse_id: "<warehouse-id>" # SQL Warehouse connection details
  catalog: "<catalog>" # Catalog for PopulationSim output tables
  schema: "<schema>" # Schema for PopulationSim output tables
```

2. config_[YEAR].yaml

Set `popsim_run_id` to the PopulationSim run to read. `popsim_landuse_table` is the Databricks table the land use is read from (`silver_mgra_based_input`). 

3. Sign in

When the land use is read from Databricks, a browser window opens to sign in with your Databricks account.
