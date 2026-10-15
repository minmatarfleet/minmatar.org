#! /bin/bash

# log something because the python app doesn't log anything on start.
echo "Starting App."

# Run the DB migration if any to run. This is dependant on the db ready to go on start.
python3 manage.py migrate

# PilotFeature rows are defined in code. Deploy does not otherwise sync them,
# so a new affiliation feature (campaigns.view) 403s until this runs.
python3 manage.py sync_pilot_features

# run the app
python3 -m gunicorn app.wsgi:application -b 0.0.0.0:8000 -w 8