FROM python:3.12.2-slim-bullseye

RUN apt-get update && apt-get install -y wget gcc g++ libssl-dev libbz2-dev unzip cmake

WORKDIR /opt/mariadb
RUN wget https://archive.mariadb.org/connector-c-3.3.1/mariadb-connector-c-3.3.1-src.zip
RUN unzip mariadb-connector-c-3.3.1-src.zip 
WORKDIR /opt/mariadb/mariadb-connector-c-3.3.1-src
RUN cmake . -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
RUN make
RUN make install
RUN mv /usr/local/lib/mariadb/* /usr/local/lib/.
ENV LD_LIBRARY_PATH=/usr/local/lib

WORKDIR /opt/app
RUN pip3 install zeroc-ice mariadb
RUN wget -O Murmur.ice "https://raw.githubusercontent.com/mumble-voip/mumble/1.4.x/src/murmur/Murmur.ice"
RUN slice2py --checksum -I/usr/local/share/Ice -I/usr/share/Ice/slice -I/usr/share/ice/slice -I/usr/share/slice /opt/app/Murmur.ice 

COPY . .

CMD ["python3", "-u", "main.py"]