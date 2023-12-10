FROM python:3.10.12-slim-buster

# install git for doctine pulling 
RUN apt-get update && apt-get install -y git
RUN apt-get -y install libmariadb-dev
RUN apt-get -y install gcc

# add user and set up repos
RUN adduser --disabled-password --gecos '' minmatar
RUN mkdir -p /opt/minmatar
COPY ./ /opt/minmatar/
RUN cp /opt/minmatar/app/app/settings.py.example /opt/minmatar/app/app/settings.py

# install reqs 
RUN pip install pipenv
WORKDIR /opt/minmatar
RUN pipenv requirements > requirements.txt
RUN pip3 install -r requirements.txt

# collect static
WORKDIR /opt/minmatar/app
RUN pipenv run python manage.py collectstatic --noinput

# keep open for debugging
CMD ["tail", "-f", "/dev/null"]