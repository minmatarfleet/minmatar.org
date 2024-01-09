FROM python:3.10.12-slim-buster

# install git for doctine pulling and various other dependencies
RUN apt-get update && apt-get install -y git libmariadb-dev gcc

# add user and set up repos
WORKDIR /opt/minmatar
COPY ./ /opt/minmatar/
#TODO - what is the purpose of adding this user here? seems like root is what is actually used.
WORKDIR /opt/minmatar/app
RUN adduser --disabled-password --gecos '' minmatar && \
  cp /opt/minmatar/app/app/settings.py.example /opt/minmatar/app/app/settings.py && \
  chmod +x container-start.sh && \
  pip install pipenv && \
  pipenv requirements > requirements.txt && \
  pip3 install -r requirements.txt && \
  python3 manage.py collectstatic --noinput


ENTRYPOINT ["./container-start.sh"]