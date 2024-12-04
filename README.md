# dssat_service_scripts

This repo contains the next scripts needed to operate the SERVIR DSSAT Service. The scripts are described next. They are listed in the same order they must be run.
 - **update_weather.py**: updates the weather database.
 - **run_forecast.py**: runs the forecast using the latest weather forecast.
 - **post_process.py**: process the forecast files created by the run_forecast.py script.
 - **update_forecast_db.py**: upload the latest forecast to the database.

The **forecast_params.json** contains some parameters needed by the scripts. 

## License and Distribution

DSSAT Service is distributed by SERVIR under the terms of the MIT License. See
[LICENSE](https://github.com/SERVIR/SAMS/blob/master/LICENSE) in this directory for more information.

## Privacy & Terms of Use

DSSAT Service abides to all of SERVIR's privacy and terms of use as described
at [https://servirglobal.net/Privacy-Terms-of-Use](https://servirglobal.net/Privacy-Terms-of-Use).
