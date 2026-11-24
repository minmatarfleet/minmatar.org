"""Settings from the environment (docker-compose-prod.yml and .env)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    redis_url: str
    ice_host: str
    ice_port: int
    ice_secret: str
    callback_host: str
    callback_port: int
    internal_url: str
    internal_secret: str
    cert_file: str
    key_file: str
    health_port: int
    server_id: int
    tick_seconds: float
    sentry_dsn: str


def from_env() -> Config:
    env = os.environ.get
    return Config(
        redis_url=env("VOICE_REDIS_URL", "redis://redis:6379/3"),
        ice_host=env("VOICE_ICE_HOST", "voice-murmur"),
        ice_port=int(env("VOICE_ICE_PORT", "6502")),
        ice_secret=env("VOICE_ICE_SECRET", ""),
        callback_host=env("VOICE_CALLBACK_HOST", "voice-auth"),
        callback_port=int(env("VOICE_CALLBACK_PORT", "6503")),
        internal_url=env("VOICE_INTERNAL_URL", "http://edge:8001/api/voice/internal"),
        internal_secret=env("VOICE_INTERNAL_SECRET", ""),
        cert_file=env("VOICE_CERT_FILE", ""),
        key_file=env("VOICE_KEY_FILE", ""),
        health_port=int(env("VOICE_HEALTH_PORT", "8080")),
        server_id=int(env("VOICE_SERVER_ID", "1")),
        tick_seconds=float(env("VOICE_TICK_SECONDS", "5")),
        sentry_dsn=env("SENTRY_DSN", ""),
    )
