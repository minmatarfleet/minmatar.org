"""``/health`` for the Docker healthcheck, the Redis heartbeat Django
watches (``voice.tasks.heartbeat_check``), and the watchdog that exits the
process when the main loop stalls.

The main loop calls ``Health.tick()`` after every iteration. If it stops
(a call into Murmur that never returns), ``/health`` answers 503 and the
watchdog dumps every thread's stack and exits, so ``restart: always``
brings the service back. Docker never restarts a container that is only
"unhealthy".
"""

from __future__ import annotations

import faulthandler
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from voice_auth.records import HEARTBEAT_KEY

logger = logging.getLogger(__name__)


class Health:
    def __init__(self, stall_seconds: float = 60.0, clock=time.monotonic):
        self.ice_connected = False
        self.authenticator = False
        self.redis_ok = False
        self.sessions = 0
        self.stall_seconds = stall_seconds
        self._clock = clock
        self.last_tick = clock()

    def tick(self) -> None:
        """The main loop finished an iteration (connected or not)."""
        self.last_tick = self._clock()

    def loop_age(self) -> float:
        return self._clock() - self.last_tick

    @property
    def stalled(self) -> bool:
        return self.loop_age() > self.stall_seconds

    @property
    def healthy(self) -> bool:
        return (
            self.ice_connected
            and self.authenticator
            and self.redis_ok
            and not self.stalled
        )

    def payload(self) -> dict:
        return {
            "at": datetime.now(timezone.utc).isoformat(),
            "ice": self.ice_connected,
            "authenticator": self.authenticator,
            "redis": self.redis_ok,
            "sessions": self.sessions,
            "loop_age": round(self.loop_age(), 1),
            "stalled": self.stalled,
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


class Watchdog:
    """Exit the process once the main loop has stalled.

    A stuck call into Murmur leaves the process up and /health answering,
    so nothing else would restart it. Before exiting it dumps every
    thread's Python stack to stderr, to show which call was stuck.
    """

    def __init__(self, health: Health, exit_process=os._exit, dump=None):
        self.health = health
        self.exit_process = exit_process
        self.dump = dump or (
            lambda: faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        )

    def check(self) -> bool:
        """Exit if stalled. True when it decided to exit."""
        if not self.health.stalled:
            return False
        logger.critical(
            "Voice service main loop stalled for %.0f s; exiting so Docker restarts it",
            self.health.loop_age(),
        )
        for handler in logging.getLogger().handlers:
            handler.flush()
        self.dump()
        self.exit_process(1)
        return True

    def start(self, interval: float = 5.0) -> threading.Thread:
        def loop():
            while True:
                time.sleep(interval)
                self.check()

        thread = threading.Thread(target=loop, name="watchdog", daemon=True)
        thread.start()
        return thread
