#! /bin/bash

# log something because the python app doesn't log anything on start.
echo "Starting App."

# Run the DB migration if any to run. This is dependant on the db ready to go on start.
python3 manage.py migrate

# run the app
python3 -m uvicorn app.asgi:application --host 0.0.0.0 --port 8000 --workers 8