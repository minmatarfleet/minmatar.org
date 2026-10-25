"""Container healthcheck for zero-downtime deploys (scripts/deploy.sh).

Traefik only routes to healthy containers, and `docker rollout` waits for the
new container to be healthy before it stops the old one.

- /tmp/drain (written by the rollout pre-stop hook) fails the check, so
  Traefik stops sending requests before the old container is stopped.
- Until the first success, Django must answer an HTTP request: migrations
  have run and the workers have imported the app. Any status counts, since
  ALLOWED_HOSTS may reject this Host header.
- After that, only the listening socket is checked, so a burst of slow
  requests that keeps every gunicorn worker busy does not mark the only
  container unhealthy and take the API offline.
"""

import http.client
import os
import socket
import sys

PORT = 8000
DRAIN_FILE = "/tmp/drain"
READY_FILE = "/tmp/ready"

if os.path.exists(DRAIN_FILE):
    sys.exit(1)

if os.path.exists(READY_FILE):
    socket.create_connection(("127.0.0.1", PORT), timeout=4).close()
    sys.exit(0)

connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=4)
connection.request("HEAD", "/")
connection.getresponse()
with open(READY_FILE, "w", encoding="utf-8"):
    pass
