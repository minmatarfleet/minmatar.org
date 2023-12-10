# minmatar.org
Platform for Minmatar Fleet

# Prerequisites
- Install Python
- Install Docker and Docker Desktop (Mac, WSL)
- Install Docker Compose
- Install `pyenv` on your machine (e.g `brew install pyenv`, google for other operating systems)
- Install `pipenv` on your machine (e.g `pip install --user --upgrade pipenv`)
- Install `pre-commit` on your machine (e.g `brew install`)

# Commands
- `for x in $(sed -e 's/#.*//' .env | grep '=') ; do export $x ; done` for populating env from .env