from dssatservice.dssat import run_spatial_dssat

import pandas as pd
import os
from datetime import datetime
from spatialDSSAT.run import GSRun
from datetime import datetime, timedelta

COUNTRY = "zimbabwe"
selected_cultivars = pd.read_csv(f"experiments/baseline_runs/{COUNTRY}_selected_cultivars.csv")
CULTIVAR_LIST = selected_cultivars.loc[selected_cultivars.best].cultivar.unique()
ADMIN1_LIST = selected_cultivars.admin1.unique()
PLANTING_MONTHS = selected_cultivars.groupby("admin1").month.median().astype(int)
YEARS = (2018, 2019, 2020, 2021, 2022)
DBNAME = "dssatserv"
SIM_CONTROLS = {"WATER": "N", "NITRO": "N"}


def get_dssat_inputs(admin1, year):
    MONTH_START = PLANTING_MONTHS.loc[admin1] - 1
    inputs = run_spatial_dssat(
        dbname=DBNAME, 
        schema=COUNTRY, 
        admin1=admin1,
        plantingdate=datetime(year, MONTH_START, 1),
        cultivar=CULTIVAR_LIST[0],
        nitrogen=[(5, 0), ],
        # overview=True,
        all_random=False,
        return_input=True
    )
    return inputs

def run_single(cultivar, plantingdate, inputs, **kwargs):
    nitro = [(0, 0),]
    gs = GSRun()
    for (_, wth), (_, sol) in inputs:
        gs.add_treatment(
            soil_profile=sol,
            weather=wth,
            nitrogen=nitro,
            planting=plantingdate,
            cultivar=cultivar
        )
    df = gs.run(
        start_date=plantingdate,
        sim_controls=SIM_CONTROLS
    )
    # overview = parse_overview("".join(gs.overview))
    df["planting_date"] = [
        l[:7].strip().title() 
        for l in filter(lambda x: "Sowing" in x, gs.overview)
    ]
    return df

def run_single_admin(admin1):
    df_list = []
    for year in YEARS:
        inputs = get_dssat_inputs(admin1, year)
        plantingdate = datetime(year, PLANTING_MONTHS.loc[admin1], 1)
        for cultivar in CULTIVAR_LIST:
            tmp_df = run_single(cultivar, plantingdate, inputs)
            tmp_df["admin1"] = admin1
            tmp_df["cultivar"] = cultivar
            tmp_df["year"] = year
            df_list.append(tmp_df)
    return pd.concat(df_list, ignore_index=True)      

# out = run_single_admin(ADMIN1_LIST[1])
# print()

def wrap_run(admin1):
    out = run_single_admin(admin1)
    out.to_csv(f"experiments/parameters/{COUNTRY}/cultivar_characterization/{admin1}.csv", index=False)
    
# wrap_run(ADMIN1_LIST[1])
from multiprocessing import Pool
p = Pool(16)
with p:
    p.map(wrap_run, ADMIN1_LIST)
print("Done!")