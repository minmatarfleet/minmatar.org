FROM python:3.10.12-slim-bookworm

# install git for doctine pulling and various other dependencies
RUN apt-get update && apt-get install -y git libmariadb-dev gcc

# add user and set up repos
WORKDIR /opt/bot
COPY . /opt/bot/
#TODO - what is the purpose of adding this user here? seems like root is what is actually used.
WORKDIR /opt/bot
RUN adduser --disabled-password --gecos '' bot && \
    pip install pipenv && \
    pipenv requirements > requirements.txt && \
    pip3 install -r requirements.txt 

# keep open for debugging
CMD ["tail", "-f", "/dev/null"]
