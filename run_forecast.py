from dssatservice.dssat import run_spatial_dssat
from dssatservice.data.transform import parse_overview
import psycopg2 as pg
from datetime import datetime, timedelta
import rioxarray as rio
from spatialDSSAT.run import GSRun
import pandas as pd
import numpy as np
import geopandas as gpd

import json
with open("forecast_params.json", "r") as f:
    params = json.load(f)
    
# COUNTRY = "Kenya"
# SEASON = "SHORT_RAINS"
COUNTRY = "Zimbabwe"
SEASON = "MAIN"
params = params[COUNTRY]

DATA_PATH = params["DATA_PATH"]
NITROGEN_RATES_PATH = params["NITROGEN_RATES_PATH"] # Must have nitrogen rates in the nitro column, and admin unit name in the admin1 column
NITRO_ADMIN_COL = params["NITRO_ADMIN_COL"]
N_RATIO = params["N_RATIO"] # Scale factor for Nitrogen input 

GEO_PATH = params["GEO_PATH"] # Must have the 
GEO_ADMIN_COL = params["GEO_ADMIN_COL"]
ADMIN_TO_REMOVE = params["ADMIN_TO_REMOVE"] # Counties that I know that cause issues
# Parameters that change with season
CULTIVARS_PATH = params["SEASONS"][SEASON]["CULTIVARS_PATH"] # Cultivars with columns admin1, cultivar, crps, ss, los, cultivar_type
CUL_ADMIN_COL = params["CUL_ADMIN_COL"]
PLANTING_DATES_PATH = params["SEASONS"][SEASON]["PLANTING_DATES_PATH"] # Start of season tiff with SOS as day of year. 
MONTH_START = params["SEASONS"][SEASON]["MONTH_START"] # Start DSSAT weather files from that month

YEAR = 2024
FORECAST_DIR = "/home/dquintero/dssat_service/forecast_data/"


SEASON_NAMES = {
    "SHORT_RAINS": "Short rains",
    "LONG_RAINS": "Long rains",
    "MAIN": "Main"
}
con = pg.connect(dbname="dssatserv")

cur = con.cursor()
cur.execute(f"SELECT admin1 FROM {COUNTRY}.admin;")
counties = [r[0] for r in cur.fetchall()]
cur.close()

for c in ADMIN_TO_REMOVE: 
    counties.remove(c)

nitrogen_df = pd.read_csv(NITROGEN_RATES_PATH)
nitrogen_df = nitrogen_df.fillna(0.)
# nitrogen_df = nitrogen_df.set_index("County")
nitrogen_df = nitrogen_df.set_index(NITRO_ADMIN_COL)
cultivars_df = pd.read_csv(CULTIVARS_PATH)
cultivars_df = cultivars_df.set_index(CUL_ADMIN_COL)

planting = rio.open_rasterio(PLANTING_DATES_PATH)

geodf = gpd.read_file(GEO_PATH)
geodf = geodf.set_index(GEO_ADMIN_COL)

def get_dssat_inputs(admin1, startdate):
    inputs = run_spatial_dssat(
        con=con, 
        schema=COUNTRY, 
        admin1=admin1,
        plantingdate=startdate,
        cultivar=None, # We're only getting files
        nitrogen=[(0, 0), ],
        # overview=True,
        all_random=True,
        return_input=True,
        nens=99
    )
    return inputs

N_FERT_APPS = 3
def run_single(admin1, inputs, year, start_date, **kwargs):
    cultivars = cultivars_df.loc[[admin1], "cultivar"].values
    # nitrogen_rate = int(N_RATIO*nitrogen_df.loc[admin1, "avg"])
    nitrogen_rate = int(N_RATIO*nitrogen_df.loc[admin1, "nitro"])
    nitrogen_rate = int(nitrogen_rate/3)
    gs = GSRun()
    # average planting date, just in case we need it
    pl_data = planting.rio.clip(geodf.loc[[admin1], "geometry"].buffer(.1))
    if hasattr(pl_data, "_FillValue"):
        avg_pd = np.nanmean(np.where(
            (pl_data == pl_data._FillValue), 
            np.nan, pl_data.data
        ))
    else:
        avg_pd = np.nanmean(pl_data)
    # avg_pd = (avg_pd - 36)*10
    pl_dates = []
    
    for (pixel, wth), (_, sol) in inputs:
        sos_doy = np.nan
        x, y = pixel
        sos_doy =float((planting.sel(x=x, y=y, method="nearest")))
        if np.isnan(sos_doy):
            sos_doy = avg_pd
        plantingdate = datetime(year, 1, 1) + timedelta(days=int(sos_doy))
        cultivar = np.random.choice(cultivars)
        los = cultivars_df.loc[[admin1]].set_index("cultivar").loc[cultivar, "los"]
        fert_timerange = int(.7*los/N_FERT_APPS)
        nitro = [(0+i*fert_timerange, nitrogen_rate) for i in range(N_FERT_APPS)]
        gs.add_treatment(
            soil_profile=sol,
            weather=wth,
            nitrogen=nitro,
            planting=plantingdate,
            cultivar=cultivar
        )
        pl_dates.append(plantingdate)
        # start_date = min(start_date, plantingdate)
    # sim_controls = kwargs.get("sim_controls", sim_controls)
    df = gs.run(
        start_date=start_date,
        latest_date=start_date + timedelta(360),
    )
    df["planting"] = pl_dates
    return df, gs.overview

YEAR = 2024
# 
# admin1 = "Bomet"
#To have files starting exactly on Jan 01
# start_date = datetime(year, 1, 1) + timedelta(30)
results = []
overviews = []
# counties = ["Nyandarua"] # TODO: REMOVE, I'm debugging

# from dssatservice import database as db
# import psycopg2 as pg

# con = pg.connect(database="dssatserv")
# problem_counties = []
# for admin1 in counties[:]:
    
#     soils = db.get_soils(con, COUNTRY, admin1, 1)
#     if len(soils) <= 4:
#         problem_counties.append(admin1)
#     continue

for admin1 in counties[:]:
    min_planting = (
        planting.rio.clip(geodf.loc[[admin1], "geometry"].buffer(.1)).min()
    )
    start_date = datetime(YEAR, 1, 1) + timedelta(int(min_planting))
    inputs = get_dssat_inputs(admin1, start_date)
    df, overview = run_single(admin1, inputs, YEAR, start_date)
    overview = parse_overview(''.join(overview))
    # df = df.loc[(df.FLO != "-99") & (df.MAT != "-99")]
    df["admin1"] = admin1
    overview["admin1"] = admin1
    results.append(df)
    overviews.append(overview)

datesuffix = datetime.today().strftime("%Y%m%d")
results = pd.concat(results, ignore_index=True)
results["season"] = SEASON_NAMES[SEASON]
results.to_csv(
    f"{FORECAST_DIR}/{COUNTRY.title()}/forecast_{datesuffix}.csv", 
    index=False
)
overviews = pd.concat(overviews, ignore_index=True)
overviews.to_csv(
    f"{FORECAST_DIR}/{COUNTRY.title()}/forecast_overview_{datesuffix}.csv",
    index=False
)
exit()

