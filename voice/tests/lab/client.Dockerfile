FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libopus0 openssl && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pymumble==1.6.1 redis==5.0.8
WORKDIR /lab
