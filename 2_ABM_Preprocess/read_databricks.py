"""
Reads one PopSim run's rows from a Databricks table (by default
popsim_landuse_table in the config) into a pandas DataFrame, optionally saving
them to CSV or Parquet.


Authentication uses the DEFAULT profile in ~/.databrickscfg (created by
`databricks auth login`). Set DATABRICKS_CONFIG_PROFILE to use another profile.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml
from databricks import sql
from databricks.sdk.core import Config

# -----------------------------------------------------------------------
# HOW TO RUN FOR TESTING DATABRICKS CONNECTION
# -----------------------------------------------------------------------
#   From the repository root, update the Conda environment:
#       conda env update --name landuse --file environment.yml
#   Update secrets.yml with Databricks connection information.
#   secrets.yml is located at the repository root (git-ignored).
#         warehouse_id: "<warehouse-id>"
#         catalog: "<catalog>"
#         schema: "<schema>"
#   Set popsim_run_id in config_year.yaml (or pass --config if the config was renamed).
#
#   Usage:    python 2_ABM_Preprocess/read_databricks.py [options]
#   Example:  python 2_ABM_Preprocess/read_databricks.py --output output/mgra_based_input.csv
#   Example (renamed config):
#             python 2_ABM_Preprocess/read_databricks.py --config config_2022.yaml
#   Example (another table):
#             python 2_ABM_Preprocess/read_databricks.py --table silver_synthetic_persons --output persons.parquet
# -----------------------------------------------------------------------

SECRETS_PATH = Path(__file__).parent.parent / "secrets.yml"
CONFIG_PATH = Path(__file__).parent.parent / "config_year.yaml"


def load_secrets():
    """Return the databricks section of secrets.yml (warehouse_id, catalog, schema)."""
    secrets = {}
    if SECRETS_PATH.exists():
        with open(SECRETS_PATH, "r") as file:
            secrets = yaml.safe_load(file) or {}
    databricks = secrets.get("databricks") or {}
    for key in ("warehouse_id", "catalog", "schema"):
        if not databricks.get(key):
            raise ValueError(f"Set databricks.{key} in {SECRETS_PATH}")
    return databricks


def quote_identifier(name):
    """Return name as a backtick-quoted SQL identifier, escaping any backticks in it."""
    name = str(name)
    if not name:
        raise ValueError("Catalog/schema/table name is empty")
    return "`" + name.replace("`", "``") + "`"


def read_run(run_id, table):
    """Return every row of catalog.schema.table where run_id = run_id.

    The catalog, schema and warehouse_id come from the databricks section of secrets.yml.
    """
    secrets = load_secrets()
    catalog, schema = secrets["catalog"], secrets["schema"]

    # Table names can't be query parameters, so they're quoted and escaped instead
    full_name = ".".join(quote_identifier(name) for name in (catalog, schema, table))

    cfg = Config()
    query = f"SELECT * FROM {full_name} WHERE run_id = :run_id"

    with sql.connect(
        server_hostname=cfg.host.removeprefix("https://"),
        http_path=f"/sql/1.0/warehouses/{secrets['warehouse_id']}",
        credentials_provider=lambda: cfg.authenticate,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, {"run_id": int(run_id)})
            return cursor.fetchall_arrow().to_pandas()


def save(df, path):
    """Write df to path as Parquet (.parquet) or CSV (anything else)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if path.lower().endswith(".parquet"):
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read one PopSim run's rows from a Databricks table."
    )
    parser.add_argument("--config", default=CONFIG_PATH, help="Config file with popsim_run_id (default: config_year.yaml)")
    parser.add_argument("--table", help="Table to read (default: popsim_landuse_table in config)")
    parser.add_argument("--output", help="Save to this .csv or .parquet file")
    args = parser.parse_args()

    try:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        parser.error(f"Config file not found: {args.config} (pass --config if it was renamed)")
    run_id = config.get("popsim_run_id")
    if run_id is None:
        parser.error(f"Set popsim_run_id in {args.config}")
    if args.table is None:
        args.table = config.get("popsim_landuse_table")
        if not args.table:
            parser.error(f"Set popsim_landuse_table in {args.config} or pass --table")
    try:
        secrets = load_secrets()
    except ValueError as e:
        parser.error(str(e))
    full_name = f"{secrets['catalog']}.{secrets['schema']}.{args.table}"

    try:
        df = read_run(run_id, table=args.table)
    except Exception as e:
        print(f"Failed to read {full_name}: {e}", file=sys.stderr)
        if (getattr(e, "context", None) or {}).get("http-code") == 403:
            print(
                "HTTP 403 from the SQL warehouse: the workspace rejected this network "
                "(e.g. off VPN), or you lack CAN USE on the warehouse",
                file=sys.stderr,
            )
        sys.exit(1)

    print(f"{len(df):,} rows for run_id {run_id} from {full_name}")
    if df.empty:
        print("No rows: check the run_id exists in this schema's run_info", file=sys.stderr)
    if args.output:
        save(df, args.output)
        print(f"Saved to {args.output}")
    else:
        print(df.head())
