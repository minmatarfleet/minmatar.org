FROM python:3.12.2-slim-bullseye

WORKDIR /opt/app

RUN apt-get update && apt-get install -y wget gcc g++ libssl-dev libbz2-dev sqlite3
RUN pip3 install zeroc-ice
RUN wget -O Murmur.ice "https://raw.githubusercontent.com/mumble-voip/mumble/1.4.x/src/murmur/Murmur.ice"
RUN slice2py --checksum -I/usr/local/share/Ice -I/usr/share/Ice/slice -I/usr/share/ice/slice -I/usr/share/slice /opt/app/Murmur.ice 

COPY . .

CMD ["python3", "-u", "main.py"]