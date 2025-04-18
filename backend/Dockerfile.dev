FROM python:3.10.12-slim-bookworm

# install git for doctine pulling and various other dependencies
RUN apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install --fix-missing -y git libmariadb-dev gcc
    
# add user and set up repos
WORKDIR /opt/minmatar
COPY . /opt/minmatar/
#TODO - what is the purpose of adding this user here? seems like root is what is actually used.
WORKDIR /opt/minmatar
RUN adduser --disabled-password --gecos '' minmatar && \
  # cp /opt/minmatar/app/settings.py.example /opt/minmatar/app/settings.py && \
  chmod +x app-start.sh && \
  python3 -m pip install --upgrade pip && \
  pip install pipenv && \
  pipenv install --system --deploy --ignore-pipfile && \
  python3 manage.py collectstatic --noinput

# keep open for debugging
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
