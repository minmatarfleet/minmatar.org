"""Stands in for Django's /api/voice/internal/ in the lab (run.sh)."""

import json

import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

r = redis.Redis(host="lab-redis", db=3)
TOKENS = {"good-token": 7, "good-token-2": 7, "banned-token": 9}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("X-Voice-Secret") != "x":
            self.send_response(401)
            self.end_headers()
            return
        record = None
        if self.path.endswith("/redeem") and body.get("password") in TOKENS:
            ident = TOKENS.pop(body["password"])
            char = r.get(f"voice:identity:{ident}").decode()
            record = json.loads(r.get(f"voice:char:{char}"))
            if body.get("cert_hash"):
                r.set(f"voice:cert:{body['cert_hash']}", ident)
        if record is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"{}")
            return
        out = json.dumps(record).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


HTTPServer(("0.0.0.0", 8001), H).serve_forever()
