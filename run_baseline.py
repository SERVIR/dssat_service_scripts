from dssatservice.dssat import run_spatial_dssat

import pandas as pd
import os
from datetime import datetime

country = "zimbabwe"
selected_cultivars = pd.read_csv(f"experiments/baseline_runs/{country}_selected_cultivars.csv")
selected_cultivars = selected_cultivars.set_index(["admin1", "cultivar"])

ADMIN1_LIST = selected_cultivars.index.get_level_values(0).unique()
DBNAME = "dssatserv"
obs = pd.read_csv("/home/dquintero/dssat_service/fewsnet_data/zimbabwe_main_maize.csv")
# obs = pd.read_csv("/home/dquintero/dssat_service/fewsnet_data/kenya_longRains_maize.csv")
# obs["admin_1"] = obs["admin_2"]
# Match records to planting dates in Zimbabwe
# obs["year"] = obs.year - 1
# obs = obs.loc[obs.season_name == "Long rains harvest"]
# obs = obs.loc[obs.year > 2010]
YEARS = range(2010, 2022)
def run_single_admin(admin1):
    df_list = []
    pars = selected_cultivars.loc[(admin1, )]
    pars = pars.loc[pars.best].iloc[0]
    nitro = pars.nitro/3
    for year in YEARS:
        tmp_df = run_spatial_dssat(
            dbname=DBNAME, 
            schema=country, 
            admin1=admin1,
            plantingdate=datetime(year, pars.month, 1),
            cultivar=pars.name,
            nitrogen=[(0, nitro), (30, nitro), (60, nitro)],
            all_random=True
        )
        tmp_df["admin1"] = admin1
        tmp_df["year"] = year
        df_list.append(tmp_df)
    return pd.concat(df_list, ignore_index=True)      

# out = run_single_admin(ADMIN1_LIST[1])
# print()

def wrap_run(admin1):
    out = run_single_admin(admin1)
    out.to_csv(f"experiments/baseline_runs/{country}/{admin1}.csv", index=False)
from multiprocessing import Pool
p = Pool(16)
with p:
    p.map(wrap_run, ADMIN1_LIST)
print("Done!")