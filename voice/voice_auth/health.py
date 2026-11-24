"""``/health`` for the Docker healthcheck, and the Redis heartbeat Django
watches (``voice.tasks.heartbeat_check``)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from voice_auth.records import HEARTBEAT_KEY


class Health:
    def __init__(self):
        self.ice_connected = False
        self.authenticator = False
        self.redis_ok = False
        self.sessions = 0

    @property
    def healthy(self) -> bool:
        return self.ice_connected and self.authenticator and self.redis_ok

    def payload(self) -> dict:
        return {
            "at": datetime.now(timezone.utc).isoformat(),
            "ice": self.ice_connected,
            "authenticator": self.authenticator,
            "redis": self.redis_ok,
            "sessions": self.sessions,
        }

    def beat(self, redis) -> None:
        try:
            redis.set(HEARTBEAT_KEY, json.dumps(self.payload()), ex=300)
            self.redis_ok = True
        except Exception:  # pylint: disable=broad-exception-caught
            self.redis_ok = False


def serve(health: Health, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(health.payload()).encode()
            self.send_response(200 if health.healthy else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep request logs (and IPs) out
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
