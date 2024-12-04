"""
This updates the latest_forecast table in the service database. This script is
run after the postprocess_forecast.py script using the same arguments. Example:

    python update_forecast_db.py Kenya SHORT_RAINS 20241202

It might be necessary to kill all the idle postgres processes, and then restart 
the webservice in the VM that host the web service.
"""
import dssatservice.database as db

from datetime import datetime
import psycopg2 as pg

import pandas as pd
import sys

try:
    COUNTRY = str(sys.argv[1])
    SEASON = str(sys.argv[2])
    DATE_SUFFIX = str(sys.argv[3])
except IndexError:
    print(
        "ERROR: No input parameters defined.\n"
        "Usage: python update_forecast_db.py COUNTRY SEASON_NAME DATE_SUFFIX\n"
        "Example:\n"
        "python update_forecast_db.py Kenya SHORT_RAINS 20241202"
    )
    raise 

con = pg.connect(dbname="dssatserv")
schema = COUNTRY.lower()
suffix = DATE_SUFFIX
country = COUNTRY
# This piece of code is to upload the latest forecast tables to the db
# Forecast map
file = f"/home/dquintero/dssat_service/forecast_data/{country}/latest_forecast.geojson"
db.add_latest_forecast(con, schema, file)
# All simulations results
results_df = pd.read_csv(
    f"/home/dquintero/dssat_service/forecast_data/{country}/forecast_{suffix}.csv"
)
db.dataframe_to_table(
    f"postgresql+psycopg2://{con.info.user}:eQY3_Fwd@localhost:{con.info.port}/{con.info.dbname}",
    results_df,
    schema,
    "latest_forecast_results",
    "admin1"
)
    # Overview file info
overview_df = pd.read_csv(
    f"/home/dquintero/dssat_service/forecast_data/{country}/forecast_overview_{suffix}.csv"
)
db.dataframe_to_table(
    f"postgresql+psycopg2://{con.info.user}:eQY3_Fwd@localhost:{con.info.port}/{con.info.dbname}",
    overview_df,
    schema,
    "latest_forecast_overview",
    "admin1"
)
con.close()