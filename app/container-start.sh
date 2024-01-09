#! /bin/bash

# log something because the python app doesn't log anything on start.
echo "Starting App."

# TODO - migrate DB
# Wait for DB to be actually ready, using a probe or healthcheck condition
# Run the DB migration if any to run.

# run the app
python3 -m uvicorn app.asgi:application --host 0.0.0.0 --port 8000