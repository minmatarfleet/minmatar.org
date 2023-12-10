FROM python:3.10.12-slim-buster

# install git for doctine pulling 
RUN apt-get update && apt-get install -y git
RUN apt-get -y install libmariadb-dev
RUN apt-get -y install gcc

# add user and set up repos
RUN adduser --disabled-password --gecos '' minmatar
RUN mkdir -p /opt/minmatar.org
COPY ./ /opt/minmatar/
RUN cp /opt/minmatar/app/app/settings.py.example /opt/minmatar/app/app/settings.py

# install reqs 
# RUN pip install --user --upgrade pipenv
# WORKDIR /opt/minmatar.org
# RUN pipenv requirements > requirements.txt
# RUN pip3 install -r requirements.txt
# RUN pipenv install 

# keep open for debugging
CMD ["tail", "-f", "/dev/null"]