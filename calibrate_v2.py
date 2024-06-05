
"""
Some changes compared to previous version. Methodology changed. Mean CRPS is 
minimized. So the mehodology is as follows:

Use KY and ZW cultivars. ZW cultivars were obtained from  https://doi.org/10.1108/IJCCSM-01-2014-0005
1. Adjust RPS for each cultivar using fertilizer. For that, use only the year
    closer to the average.
2. Try different planting months
3. Select best planting month based on RPS/correlation.
4. Keep cultivars that met some correlation/rmse criteria.

All run results will be saved.
"""
# import sys 
# sys.path.append("/home/dquintero/dev_dssat_service")
from dssatservice.dssat import run_spatial_dssat
from dssatservice.data.transform import parse_overview
from dssatservice.database import connect
from spatialDSSAT.run import GSRun
from datetime import datetime, timedelta
import numpy as np
import pandas as pd 
from scipy.stats import pearsonr
import os 
os.chdir("/home/dquintero/dssat_service/web_service_dev/experiments")

COUNTRY_LIST = ["Kenya", "Zimbabwe"]

DBNAME = "dssatserv"
COUNTRY = "Kenya"
assert COUNTRY in COUNTRY_LIST

con = connect(DBNAME)
cur = con.cursor()
cur.execute(f"SELECT admin1 FROM {COUNTRY}.admin;")
rows = cur.fetchall()
cur.close()
con.close()
ADMIN1_LIST = [r[0] for r in rows]

ADMIN_EXCLUDE_DICT = { # Too small to have at least 4 pixels 
    "Kenya": ["Mombasa",],
    "Zimbabwe": ['Chinhoyi Urban', 'Kadoma Urban']
}
ADMIN1_LIST = list(filter(lambda x: x not in ADMIN_EXCLUDE_DICT[COUNTRY], ADMIN1_LIST))

CULTIVARS_DICT = {
    "Kenya": [
        'IF0001', 'IF0002', 'IF0003', 'IF0004', 'IF0005', 'IF0006', 'IF0007', 
        'IF0008', 'IF0009', 'IF0010', 'IF0011', 'IM0001', 'IM0002', 'IM0003', 
        'IF0018', 'IF0019', 'IF0020', 'IF0021', 'IF0022', 'IB0067', 
        'EM0001', 'KY0001', 'KY0002', 'KY0003', 'KY0004', 'KY0005', 'KY0006', 
        'KY0007', 'KY0008', 'KY0009', 'KY0010', 'KY0011', 'KY0012', 'KY0013', 
        'KY0014', 'KY0015', 'KY0016', 'KY0017', 'KY0018', 'GH0010',
    ],
    "Zimbabwe": [
        'ZM0001', 'ZM0002', 'ZM0003', 'KA0001', 'EM0001', 'KY0001', 'KY0002', 
        'KY0003', 'KY0004', 'KY0005', 'KY0006', 'KY0007', 'KY0008', 'KY0009', 
        'KY0010', 'KY0011', 'KY0012', 'KY0013', 'KY0014', 'KY0015', 'KY0016', 
        'KY0017', 'KY0018', 'GH0010',
    ]
    
}
CULTIVARS = CULTIVARS_DICT[COUNTRY]
# Obs data for Zimbabwe
if COUNTRY == "Zimbabwe":
    obs = pd.read_csv("~/dssat_service/fewsnet_data/zimbabwe_main_maize.csv")
    obs["admin_1"] = obs.admin_2
    obs["year"] = obs.year - 1 # Change to planting year
    PLANT_MONTHS = (11, 12)
if COUNTRY == "Kenya":
    # Data for Kenya
    obs = pd.read_csv("~/dssat_service/fewsnet_data/kenya_longRains_maize.csv")
    obs = obs.loc[obs.year > 2010]
    PLANT_MONTHS = (3, 4, 5)

obs = obs.loc[~obs.value.isna()]
ADMIN1_LIST = list(filter(lambda x: x in obs.admin_1.unique(), ADMIN1_LIST)) 


def get_dssat_inputs(admin1, year):
    MONTH_START = min(PLANT_MONTHS) - 1
    inputs = run_spatial_dssat(
        dbname=DBNAME, 
        schema=COUNTRY, 
        admin1=admin1,
        plantingdate=datetime(year, MONTH_START, 1),
        cultivar=CULTIVARS[0],
        nitrogen=[(5, 15), (30, 15), (60, 15)],
        # overview=True,
        all_random=False,
        return_input=True
    )
    return inputs

def run_single(fertilizer, cultivar, plantingdate, inputs, **kwargs):
    fertilizer = int(fertilizer)
    fertilizer = int(fertilizer/3)
    nitro = [(0, fertilizer), (30, fertilizer), (60, fertilizer)]
    gs = GSRun()
    for (_, wth), (_, sol) in inputs:
        gs.add_treatment(
            soil_profile=sol,
            weather=wth,
            nitrogen=nitro,
            planting=plantingdate,
            cultivar=cultivar
        )
    planting_window_start = plantingdate - timedelta(days=15)
    planting_window_end = plantingdate + timedelta(days=15)
    sim_controls = {
        "PLANT": "F", # Automatic, force in last day of window
        "PFRST": planting_window_start.strftime("%y%j"),
        "PLAST": planting_window_end.strftime("%y%j"),
        "PH2OL": 60, "PH2OU": 100, "PH2OD": 20, 
        "PSTMX": 40, "PSTMN": 10
    }
    sim_controls = kwargs.get("sim_controls", sim_controls)
    df = gs.run(
        start_date=plantingdate - timedelta(30),
        sim_controls=sim_controls
    )
    # overview = parse_overview("".join(gs.overview))
    df["planting_date"] = [
        l[:7].strip().title() 
        for l in filter(lambda x: "Sowing" in x, gs.overview)
    ]
    return df

def calculate_mse(admin1, fertilizer, cultivar, inputs_dict):
    residuals = []
    for _, row in obs.loc[obs.admin_1 == admin1].iterrows():
        plantingdate = datetime(row.year, 4, 1)
        df = run_single(
            fertilizer, cultivar, plantingdate, inputs_dict[row.year]
        )
        residuals.append(df.HARWT.astype(int).median()/1000 - row.value)
    return sum([r**2 for r in residuals])

def calculate_crps(admin1, fertilizer, cultivar, inputs_dict):
    """
    Calculate CRPS for the year closest to period average
    """
    obs_admin = obs.loc[obs.admin_1 == admin1].set_index("year")
    row = obs_admin.loc[
        (obs_admin.value - obs_admin.value.mean()).abs().idxmin()
    ]
    x = np.arange(0, 10000, 1)
    plantingdate = datetime(row.name, int(np.mean(PLANT_MONTHS)), 1)
    sim_controls = {
        "PLANT": "F", # Automatic, force in last day of window
        "PFRST": datetime(row.name, PLANT_MONTHS[0], 1).strftime("%y%j"),
        "PLAST": datetime(row.name, PLANT_MONTHS[-1], 28).strftime("%y%j"),
        "PH2OL": 60, "PH2OU": 100, "PH2OD": 20, 
        "PSTMX": 40, "PSTMN": 10
    }
    df = run_single(
        fertilizer, cultivar, plantingdate, inputs_dict[row.name],
        sim_controls=sim_controls
    )
    pred_vals = (df.HARWT.astype(int)).values
    hist, _ = np.histogram(pred_vals, bins=x, density=True)
    pred_cdf = hist.cumsum()
    obs_cdf = (x > row.value*1000).astype(int)
    return ((pred_cdf - obs_cdf[:-1])**2).sum()


from ax import (
    SearchSpace, RangeParameter, ParameterType,
    OptimizationConfig, Objective,
    Data, Runner, Experiment
)
from ax.metrics.noisy_function import NoisyFunctionMetric
from ax.utils.common.result import Ok
from ax.modelbridge.registry import Models
from ax.core.generator_run import GeneratorRun
from ax.core.arm import Arm 

search_space = SearchSpace([
    RangeParameter(
        name="nitro", parameter_type=ParameterType.FLOAT, 
        lower=0., upper=200.
    ),
])
param_names = ["nitro", ]
gen_first_trial = GeneratorRun(
    arms=[Arm({"nitro" : 0})]
)

def get_optimization_config(admin1, cultivar, inputs):
    class ObjectiveFunction(NoisyFunctionMetric):
        def fetch_trial_data(self, trial):
            records = []
            res = False
            for arm_name, arm in trial.arms_by_name.items():
                params = arm.parameters
            res = calculate_crps(
                admin1, params["nitro"], cultivar, inputs
            )
            records.append(
                {
                    "arm_name": arm_name,
                    "metric_name": "crps",
                    "trial_index": trial.index,
                    "mean": res,
                    "sem": 0,
                }
            )
            return Ok(value=Data(df=pd.DataFrame.from_records(records)))

        def is_available_while_running(self) -> bool:
            return False
    optimization_config = OptimizationConfig(
        objective= Objective(
            metric=ObjectiveFunction(
                name="crps", param_names=param_names
            ),  
            minimize=True
        ),
    )
    return optimization_config

NUM_SOBOL_TRIALS = 4
NUM_BOTORCH_TRIALS = 5
def optimize_nitrogen(admin1, cultivar, inputs):
    optimization_config = get_optimization_config(
        admin1, cultivar, inputs
    )
    class MyRunner(Runner):
        def run(self, trial):
            trial_metadata = {"name": str(trial.index)}
            return trial_metadata
    exp = Experiment(
        name="optimize_nitro",
        search_space=search_space,
        optimization_config=optimization_config,
        runner=MyRunner(),
    )
    # First trial with nitro = 0
    trial = exp.new_trial(generator_run=gen_first_trial)
    trial.run()
    trial.mark_completed()
    sobol = Models.SOBOL(search_space=exp.search_space)
    for _ in range(NUM_SOBOL_TRIALS):
        generator_run = sobol.gen(n=1)
        trial = exp.new_trial(generator_run=generator_run)
        trial.run()
        trial.mark_completed()

    data = exp.fetch_data()
    for _ in range(NUM_BOTORCH_TRIALS):
        # Reinitialize GP+EI model at each step with updated data.
        gpei = Models.BOTORCH_MODULAR(experiment=exp, data=data)
        generator_run = gpei.gen(n=1)
        trial = exp.new_trial(generator_run=generator_run)
        trial.run()
        trial.mark_completed()
        data = exp.fetch_data()
    
    results = []
    for _, trial in exp._trials.items():
        results.append((
            trial.arm.parameters['nitro'],
            trial.get_metric_mean("crps")   
        ))
    results = pd.DataFrame(results, columns=["nitro", "crps"])
    return results.loc[results.crps.idxmin(), "nitro"]

Z_LIM = .44
QUANTILES = np.arange(0.025, 1, 0.05)
def get_simulated_probs(df):
    yld_sim = (
        df
        .groupby("year")
        .HARWT.quantile(QUANTILES)
        .sort_index()
    )
    yld_ref = (
        yld_sim
        .reset_index()
        .rename(columns={"level_1": "quantile"})
        .groupby(["quantile"])
        .HARWT.agg(("mean", "std"))
    )
    std_yield_sim = \
        (
            yld_sim - yld_sim.index.get_level_values(1).map(
                yld_ref.reset_index().set_index("quantile")["mean"]
            )
        ) / \
        yld_sim.index.get_level_values(1).map(
            yld_ref.reset_index().set_index("quantile")["std"]
        )
    yld_cats_sim = pd.Series(np.where(
        std_yield_sim < -Z_LIM, 0,
        np.where(std_yield_sim > Z_LIM, 2, 1)
    ), index=std_yield_sim.index)
    yld_cats_sim = yld_cats_sim.reset_index().rename(columns={0: "yld_cat"})
    yld_cats_sim["prob"] = 1/len(QUANTILES)
    yld_cats_sim = pd.pivot_table(
        yld_cats_sim,
        index="year",
        columns="yld_cat",
        values="prob",
        aggfunc="sum"
    )
    yld_cats_sim = yld_cats_sim.fillna(0)
    return yld_cats_sim

def get_obs_probs(admin1):
    yld = obs.loc[obs.admin_1 == admin1].set_index("year").sort_index().value
    std_yield = (yld - yld.mean())/yld.std()
    yld_cats = pd.Series(np.where(
        std_yield < -Z_LIM, 0,
        np.where(std_yield > Z_LIM, 2, 1)
    ), index=std_yield.index)
    yld_cats
    
    yld_cats = yld_cats.reset_index().rename(columns={0: "yld_cat"})
    yld_cats["prob"] = 1
    yld_cats = pd.pivot_table(
        yld_cats,
        index="year",
        columns="yld_cat",
        values="prob",
        aggfunc="sum"
    )
    yld_cats = yld_cats.fillna(0)
    return yld_cats

def calculate_RPS(run_df, obs_prob):
    yld_cats = obs_prob
    yld_cats_sim = get_simulated_probs(run_df)
    RPS = (
        (yld_cats_sim.cumsum(axis=1) - yld_cats.cumsum(axis=1))**2
    ).sum(axis=1).mean()
    return RPS


def process_cultivar(admin1, cultivar, inputs_dict):
    records = []
    x = np.arange(0, 10000, 1)
    nitro = optimize_nitrogen(admin1, cultivar, inputs_dict)
    # nitro = 2.
    obs_prob = get_obs_probs(admin1)
    for month in PLANT_MONTHS:
        crps_list = []
        obs_yield = []
        sim_yield = []
        
        run_df = []
        for _, row in obs.loc[obs.admin_1 == admin1].iterrows():
            plantingdate = datetime(row.year, month, 1)
            df = run_single(
                nitro, cultivar, plantingdate, inputs_dict[row.year]
            )
            # 
            pred_vals = (df.HARWT.astype(int)).values
            hist, _ = np.histogram(pred_vals, bins=x, density=True)
            pred_cdf = hist.cumsum()
            obs_cdf = (x > row.value*1000).astype(int)
            crps_list.append(((pred_cdf - obs_cdf[:-1])**2).sum())
            
            sim_yield.append(df.HARWT.astype(int).median())
            obs_yield.append(row.value*1000)
            df["year"] = row.year
            df["HARWT"] = df.HARWT.astype(int)
            run_df.append(df)
            
        run_df = pd.concat(run_df, ignore_index=True)
        rps = calculate_RPS(run_df, obs_prob)
        run_df.to_csv(
            f"/home/dquintero/dssat_service/web_service_dev/experiments/parameters/{COUNTRY.lower()}/all_runs/{admin1}_{cultivar}_{month}.csv", index=False
        )
        if len(obs_yield) > 3:
            r, p =pearsonr(sim_yield, obs_yield)
        else:
            r = p = np.nan
        rmse = np.sqrt((np.array(obs_yield) - np.array(sim_yield))**2).mean()
        records.append((
            admin1, cultivar, nitro, month, r, p, rmse, np.mean(crps_list), rps
        ))
        print("{0}\t{1}\t{2:>.1f}\t{3:>}\t{4:>.3f}\t{5:>.3f}\t{6:>.3f}\t{7:>.3f}\t{8:>.3f}".format(*records[-1]))
    pd.DataFrame(
        records, 
        columns=["admin1", "cultivar", "nitro", "month", "r", "p", "rmse", "crps", "rps"]
    ).to_csv(f"/home/dquintero/dssat_service/web_service_dev/experiments/parameters/{COUNTRY.lower()}/{admin1}_{cultivar}.csv", index=False)

if __name__ == "__main__": 
    for admin1 in ADMIN1_LIST[28:]:
        inputs_dict = {}
        # import pickle
        # with open("inputs_dict_debug.pkl", "rb") as f:
        #     inputs_dict = pickle.load(f)
        for _, row, in obs.loc[obs.admin_1 == admin1].iterrows():
            inputs_dict[row.year] = get_dssat_inputs(admin1, row.year)
        # with open("inputs_dict_debug.pkl", "wb") as f:
        #     pickle.dump(inputs_dict, f)
        for cultivar in CULTIVARS:
            # cultivar = "KA0001"
            process_cultivar(admin1, cultivar, inputs_dict)
        
            