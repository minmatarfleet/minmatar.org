"""Settings from the environment (docker-compose-prod.yml and .env)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    redis_url: str
    ice_host: str
    ice_port: int
    ice_secret: str
    # The name Murmur uses to call us back (published in our proxies). The
    # callback adapter itself listens on all interfaces; see main.py.
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
    # Every call to Murmur fails after this instead of waiting forever.
    ice_timeout_ms: int = 10000
    # /health fails, and the watchdog exits the process, once the main loop
    # has not completed an iteration for this long.
    stall_seconds: float = 60.0
    # Longest Murmur's main thread waits on one login decision; after it the
    # client is told to retry. Murmur serves nobody while it waits.
    auth_deadline_seconds: float = 5.0
    # DEBUG logs every Ice call to Murmur with its duration.
    log_level: str = "INFO"


def stall_seconds_for(tick_seconds: float) -> float:
    return max(3 * tick_seconds, 60.0)


def from_env() -> Config:
    env = os.environ.get
    tick_seconds = float(env("VOICE_TICK_SECONDS", "5"))
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
        tick_seconds=tick_seconds,
        sentry_dsn=env("SENTRY_DSN", ""),
        ice_timeout_ms=int(env("VOICE_ICE_TIMEOUT_MS", "10000")),
        stall_seconds=float(
            env("VOICE_STALL_SECONDS", "") or stall_seconds_for(tick_seconds)
        ),
        auth_deadline_seconds=float(env("VOICE_AUTH_DEADLINE_SECONDS", "5")),
        log_level=env("VOICE_LOG_LEVEL", "INFO").upper(),
    )
