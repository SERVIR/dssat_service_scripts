"""
This program processes the files created with the run_forecast.py data. It 
is run by passing the country, season, and date suffix as arguments. Example:
    
    python postprocess_forecast.py Kenya SHORT_RAINS 20241202
    
In the example, the script will look for the forecast files in 
/home/dquintero/dssat_service/forecast_data/Kenya. The script creates the 
latest_forecast.geojson.
""" 

import pandas as pd
import geopandas as gpd
from datetime import datetime
import numpy as np
import sys 

# COUNTRY = "Kenya"
# SEASON = "SHORT_RAINS"
# COUNTRY = "Zimbabwe"
# SEASON = "MAIN"
FORECAST_DIR = "/home/diego/dssat_service_data/forecast_output"
# datesuffix = "20241202"

try:
    COUNTRY = str(sys.argv[1])
    SEASON = str(sys.argv[2])
    DATE_SUFFIX = str(sys.argv[3])
except IndexError:
    print(
        "ERROR: No input parameters defined.\n"
        "Usage: python postprocess_forecast.py COUNTRY SEASON_NAME DATE_SUFFIX\n"
        "Example:\n"
        "python postprocess_forecast.py Kenya SHORT_RAINS 20241202"
    )
    raise 

FORECAST_CSV_PATH = f"{FORECAST_DIR}/{COUNTRY}/forecast_{DATE_SUFFIX}.csv"


import json
with open("forecast_params.json", "r") as f:
    params = json.load(f)
    
params = params[COUNTRY]
GEO_PATH = params["GEO_PATH"]
GEO_ADMIN_COL = params["GEO_ADMIN_COL"]
NITROGEN_RATES_PATH = params["NITROGEN_RATES_PATH"]
NITRO_ADMIN_COL = params["NITRO_ADMIN_COL"]
N_RATIO = params["N_RATIO"] # Scale factor for Nitrogen input 
OBSERVED_CSV_PATH = params["SEASONS"][SEASON]["OBS_DATA"]
OBS_ADMIN_MAP = params["SEASONS"][SEASON]["OBS_ADMIN_MAP"]
OBS_ADMIN_COL = params["OBS_ADMIN_COL"]
ADMIN_TO_REMOVE = params["ADMIN_TO_REMOVE"]


nitrogen_df = pd.read_csv(NITROGEN_RATES_PATH)
nitrogen_df = nitrogen_df.set_index(NITRO_ADMIN_COL)

forecast_df = pd.read_csv(FORECAST_CSV_PATH)
forecast_df = forecast_df.set_index("admin1")
# Remove simulations that did not reach harvest. This will include crop failure
# before flowering.
forecast_df['planting'] = pd.to_datetime(forecast_df.planting)
forecast_df = forecast_df.loc[forecast_df.MAT != -99]


observed_df = pd.read_csv(OBSERVED_CSV_PATH)
observed_df = observed_df.set_index(OBS_ADMIN_COL)
observed_df.index = observed_df.index.map(lambda x: OBS_ADMIN_MAP.get(x, x))
observed_df["obs"] = 1000*observed_df.value
geodf = gpd.read_file(GEO_PATH)
geodf = geodf.set_index(GEO_ADMIN_COL)
geodf["pred"] = forecast_df.groupby(level="admin1").HARWT.mean()
# geodf = geodf.dropna()
# geodf = geodf.loc[geodf.index.isin(observed_df.index.unique())]
geodf = geodf.loc[~geodf.index.isin(ADMIN_TO_REMOVE)]

def get_yield_category(admin1):
    try:
        avg = observed_df.loc[admin1, "obs"].mean()
    except KeyError:
        return
    pred = geodf.loc[admin1, "pred"]
    if any(map(pd.isna, (avg, pred))):
        return 
    # z_score = (pred - avg)/std
    # if z_score < -1.65: # 95 %
    #     return "Very Low"
    # elif z_score < -.68: # 75 %
    #     return "Low"
    # elif z_score < .68:
    #     return "Normal"
    # elif z_score < 1.65:
    #     return "High"
    # elif z_score >= 1.65:
    #     return "Very High"
    # else:
    #     raise ValueError("Something went wrong")
    pct_score = pred/avg
    if pct_score < (1 - .75): 
        return "Very Low"
    elif pct_score < (1 - .25): 
        return "Low"
    elif pct_score < (1 + .25):
        return "Normal"
    elif pct_score < (1 + .75):
        return "High"
    elif pct_score >= (1 + .75):
        return "Very High"
    else:
        raise ValueError("Something went wrong")
    
geodf.loc[:, "pred_cat"] = geodf.index.map(get_yield_category)
geodf.loc[:, "obs_avg"] = observed_df.groupby(level=OBS_ADMIN_COL).obs.mean()
geodf.loc[:, "obs_std"] = observed_df.groupby(level=OBS_ADMIN_COL).obs.std()
geodf.loc[:, "obs_min"] = observed_df.groupby(level=OBS_ADMIN_COL).obs.min()
geodf.loc[:, "obs_max"] = observed_df.groupby(level=OBS_ADMIN_COL).obs.max()
geodf.loc[:, "obs_min"] = np.where(
    geodf.obs_std.isna(), np.nan, geodf.obs_min
)
geodf.loc[:, "obs_max"] = np.where(
    geodf.obs_std.isna(), np.nan, geodf.obs_max
)

geodf.loc[:, "planting_period"] = forecast_df.groupby(level="admin1").apply(
    lambda x: ' to '.join(
        set((
            x.planting.quantile(.1).strftime('%B'), 
            x.planting.quantile(.9).strftime('%B'))
        ))
)
geodf.loc[:, "ref_period"] = observed_df.groupby(level=OBS_ADMIN_COL).year.apply(
    lambda x: '-'.join((str(x.min()), str(x.max())))
)
geodf.loc[:, 'nitro_rate'] = nitrogen_df["nitro"] * N_RATIO
geodf.loc[:, 'urea_rate'] = geodf.nitro_rate/.46
geodf["season_name"] = forecast_df.groupby(level="admin1").season.first()
geodf.index.name = "admin1"
geodf.to_file(f"{FORECAST_DIR}/{COUNTRY}/latest_forecast.geojson")

exit()