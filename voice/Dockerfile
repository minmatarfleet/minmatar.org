# The voice service: Murmur's authenticator and reconciler over Ice.
# Its own build context, so backend changes never rebuild or restart it.
FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-zeroc-ice zeroc-ice-slice python3-redis python3-requests python3-pip \
    && pip3 install --no-cache-dir --break-system-packages sentry-sdk==2.19.2 \
    && apt-get purge -y python3-pip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/voice
COPY MumbleServer.ice ./MumbleServer.ice
COPY voice_auth ./voice_auth

# The image already has a 'voice' group (audio devices); use our own user.
RUN useradd --system --no-create-home --user-group voiceauth
USER voiceauth

ENV PYTHONUNBUFFERED=1
CMD ["python3", "-m", "voice_auth.main"]
