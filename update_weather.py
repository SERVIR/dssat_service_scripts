from dssatservice.data import ingest
import dssatservice.database as db
from datetime import datetime, timedelta


COUNTRIES = ["kenya", "zimbabwe"]
DBNAME = "dssatserv"
con = db.connect(DBNAME)
cur = con.cursor()
    
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
        ingest.ingest_era5_series(DBNAME, schema, latest, today)
        
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
                ingest.ingest_era5_record(DBNAME, schema, date)
    cur.close()
    con.close()