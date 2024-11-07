from dssatservice.data import ingest
import dssatservice.database as db
import psycopg2 as pg
from datetime import datetime, timedelta
import requests


COUNTRIES = ["kenya", "zimbabwe"]
con = pg.connect(dbname="dssatserv")
cur = con.cursor()
    
# for i in range(2, 11):
#     ingest.ingest_nmme_rain(con, "kenya", i)
# exit()
if __name__ == "__main__":
    today = datetime.today()
    for schema in COUNTRIES:
        # Download series from the latest record available up to today
        latest_dates = []
        for var in ('rain', 'tmax', 'tmin', 'srad'):
            sql = f"SELECT MAX(fdate) FROM {schema}.era5_{var};"
            cur.execute(sql)
            latest = cur.fetchone()[0]
            latest_dates.append(datetime(latest.year, latest.month, latest.day))
        latest = min(latest_dates)
        ingest.ingest_era5_series(con, schema, latest, today)
        
        # If there is any date that is missing in any of the variables it'll
        # download that data.
        for var in ('rain', 'tmax', 'tmin', 'srad'):
            sql = f"SELECT MAX(fdate) FROM {schema}.era5_{var};"
            cur.execute(sql)
            latest = cur.fetchone()[0]
            missing_dates = db.verify_series_continuity(
                con, schema, f"era5_{var}",
                datetime(2010, 1, 1), latest
            )
            for date in missing_dates:
                ingest.ingest_era5_record(con, schema, date)
                
        # Check if new NMME Data is available
        r = requests.get(
            "https://climateserv.servirglobal.net/api/getClimateScenarioInfo/"
        )
        forecast_info = r.json()["climate_DataTypeCapabilities"][0]["current_Capabilities"]
        start_date = datetime.strptime(forecast_info["startDateTime"], "%Y-%m-%d")
        end_date = datetime.strptime(forecast_info["endDateTime"], "%Y-%m-%d")
        for ens in range(1, 11):
    #     ingest.ingest_nmme_rain(con, "kenya", i)
            sql = f"SELECT MAX(fdate) FROM {schema}.nmme_rain WHERE ens={ens};"
            cur.execute(sql)
            latest = cur.fetchone()[0]
            if end_date.date() > latest:
                # ingest.ingest_nmme(con, schema)
                ingest.ingest_nmme_rain(con, schema, ens)
            sql = f"SELECT MAX(fdate) FROM {schema}.nmme_tmax WHERE ens={ens};"
            cur.execute(sql)
            latest = cur.fetchone()[0]
            if end_date.date() > latest:
                # ingest.ingest_nmme(con, schema)
                ingest.ingest_nmme_temp(con, schema, ens)
        
    cur.close()
    con.close()