#! /bin/bash

# log something because the python app doesn't log anything on start.
echo "Starting App."

# Run the DB migration if any to run. This is dependant on the db ready to go on start.
python3 manage.py migrate

# Collect static assets
python3 manage.py collectstatic --noinput

# run the app with live reload
python3 manage.py runserver 0.0.0.0:8000