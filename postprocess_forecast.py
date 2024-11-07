import pandas as pd
import geopandas as gpd
from datetime import datetime
import numpy as np

COUNTRY = "Kenya"
SEASON = "SHORT_RAINS"
FORECAST_DIR = "/home/dquintero/dssat_service/forecast_data/"

datesuffix = datetime.today().strftime("%Y%m%d")
FORECAST_CSV_PATH = f"{FORECAST_DIR}/{COUNTRY}/forecast_{datesuffix}.csv"

import json
with open("forecast_params.json", "r") as f:
    params = json.load(f)
    
COUNTRY = "Kenya"
params = params[COUNTRY]
DATA_PATH = params["DATA_PATH"]
NITROGEN_RATES_PATH = params["NITROGEN_RATES_PATH"]
GEO_PATH = params["GEO_PATH"]
N_RATIO = params["N_RATIO"] # Scale factor for Nitrogen input 
OBSERVED_CSV_PATH = params["SEASONS"][SEASON]["OBS_DATA"]
OBS_ADMIN_MAP = params["SEASONS"][SEASON]["OBS_ADMIN_MAP"]
OBS_COL_MAP = params["SEASONS"][SEASON]["OBS_COL_MAP"]
ADMIN_TO_REMOVE = params["ADMIN_TO_REMOVE"]

NITRO_COLS_RENAME = {
    "Kenya": {"County": "admin1"},
}

nitrogen_df = pd.read_csv(NITROGEN_RATES_PATH)
nitrogen_df = nitrogen_df.rename(
    columns=NITRO_COLS_RENAME[COUNTRY]).set_index("admin1")

forecast_df = pd.read_csv(FORECAST_CSV_PATH)
forecast_df = forecast_df.set_index("admin1")
# Remove simulations that did not reach harvest. This will include crop failure
# before flowering.
forecast_df['planting'] = pd.to_datetime(forecast_df.planting)
forecast_df = forecast_df.loc[forecast_df.MAT != -99]


observed_df = pd.read_csv(OBSERVED_CSV_PATH)
observed_df = observed_df.rename(
    columns=OBS_COL_MAP).set_index("admin1")
observed_df.index = observed_df.index.map(lambda x: OBS_ADMIN_MAP.get(x, x))
observed_df["obs"] = 1000*observed_df.value
geodf = gpd.read_file(GEO_PATH)
geodf = geodf.set_index("admin1")
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
geodf.loc[:, "obs_avg"] = observed_df.groupby(level="admin1").obs.mean()
geodf.loc[:, "obs_std"] = observed_df.groupby(level="admin1").obs.std()
geodf.loc[:, "obs_min"] = observed_df.groupby(level="admin1").obs.min()
geodf.loc[:, "obs_max"] = observed_df.groupby(level="admin1").obs.max()
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
geodf.loc[:, "ref_period"] = observed_df.groupby(level='admin1').year.apply(
    lambda x: '-'.join((str(x.min()), str(x.max())))
)
geodf.loc[:, 'nitro_rate'] = nitrogen_df.avg * N_RATIO
geodf.loc[:, 'urea_rate'] = geodf.nitro_rate/.46
geodf["season_name"] = forecast_df.groupby(level="admin1").season.first()

geodf.to_file(f"{FORECAST_DIR}/{COUNTRY}/latest_forecast.geojson")

exit()