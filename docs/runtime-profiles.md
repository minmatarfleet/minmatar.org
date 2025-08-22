# Overview

The code can be run in a number of different configurations, which are referred to as "profiles" here, with each profile having its own strengths and weaknesses.

## Summary

| Profile | Host | API | ESI + Discord | Data
| ------- | - | - | - | - |
| Production | docker | live  | live | live |
| Astro dev | npm | live  | (live) | (live) |
| Django dev | django | self | mock  | synth |
| Local dev | npm + django | local | alt | local |
| Standalone | docker | docker | mock  | synth | 
| Full dev | docker + npm + django | self | alt | copy

* `Host` refers to the method of launching the application, either directly using `npm` (FE) or `manage.py` (BE), or as a docker container.
* `API` identifies how the frontend connects to the backend. `live` means using the production API, `self` means the profile is the API, `local` means use the API running locally with `manage.py`, and `docker` means use the API running locally under docker.
* `ESI + Discord` describes how the code uses those external APIs. `live` uses the minmatar.org live integrations, `mock` means the integrations are mocked and `alt` means the developer provides their own access.
* `Data` refers to how the data is configured. `live` is the real production data, `synth` means synthetic (made up) test data and `copy` means a copy of live data.

## Profile Details

### Production
The live profile, as used on the production server. Runs in docker-compose, with a MariaDB database and
real connections to Discord and ESI.

### Astro Dev
For frontend (only) development, the Astro site can be run directly using NPM, configured to use the production backend (API). 

Mim uses this.

### Django Dev
For backend (only) development the Django APi can be run directly using `manage.py`. Most of the functionality, and all the unit tests, work with mocked Discord & ESI, and synthetic test data.

Silvatek uses this.

### Local Dev
Local dev is simply the combination of `Astro` dev with `Django Dev` with the Astro app configured to use the local API.

Bear uses this.

### Standalone
A fully-standalone docker-compose setup designed to be very easy for new developers to get started with. ESI and Discord are mocked, and the data is all synthetic.

The backend mounts the source code folder directly and uses live reload to pick up changes as they are made.

Silvatek maintains this.

### Full Dev
uses the developer's own ESI application credentials to access tranquility
uses the developer's own Discord Server, and own Discord application/bot and credentials.
sets up live-like data

docker compose is used to host backend dependencies of Redis and MariaDB
front end run via `npm run dev`
backend run via `manage.py` and `celery`

SmokeMeAKipper maintains this.
