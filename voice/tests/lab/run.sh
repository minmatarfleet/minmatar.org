#!/usr/bin/env bash
# Real-Murmur lab: boots mumble-server v1.5.939, this branch's voice service,
# Redis and a stub of Django's internal endpoint on an isolated network,
# then drives them with a scripted Mumble client (pymumble).
# Only 127.0.0.1 is touched; every secret here is a throwaway lab value.
set -euo pipefail
cd "$(dirname "$0")"
N=voicelab
cleanup() { docker rm -f lab-auth lab-murmur lab-redis lab-internal >/dev/null 2>&1 || true; docker network rm $N >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
docker build -q -t minmatar-voice-auth:lab ../.. >/dev/null
docker build -q -t voicelab-client -f client.Dockerfile . >/dev/null
docker network create $N >/dev/null
docker run -d --name lab-redis --network $N redis:6.0.9-alpine >/dev/null
docker run -d --name lab-murmur --network $N \
  -e "MUMBLE_CONFIG_ICE=tcp -h 0.0.0.0 -p 6502" -e MUMBLE_CONFIG_ICESECRETWRITE=labwrite \
  -e MUMBLE_CONFIG_ICESECRETREAD=labread -e MUMBLE_CONFIG_SERVERPASSWORD=labserverpw \
  -e MUMBLE_SUPERUSER_PASSWORD=labsu -e MUMBLE_CONFIG_ALLOWPING=false \
  -e MUMBLE_CONFIG_DEFAULTCHANNEL=1 -e MUMBLE_CONFIG_REMEMBERCHANNEL=false \
  mumblevoip/mumble-server:v1.5.939 >/dev/null
docker run -d --name lab-internal --network $N -v "$PWD":/lab voicelab-client python stub_internal.py >/dev/null
sleep 6
docker run -d --name lab-auth --network $N -e VOICE_REDIS_URL=redis://lab-redis:6379/3 \
  -e VOICE_ICE_HOST=lab-murmur -e VOICE_ICE_SECRET=labwrite -e VOICE_CALLBACK_HOST=lab-auth \
  -e VOICE_INTERNAL_URL=http://lab-internal:8001/api/voice/internal -e VOICE_INTERNAL_SECRET=x \
  minmatar-voice-auth:lab >/dev/null
sleep 6
docker run --rm --network $N -v "$PWD":/lab voicelab-client python client_checks.py
docker stop lab-auth >/dev/null
docker run --rm --network $N -v "$PWD":/lab voicelab-client python fail_closed.py
