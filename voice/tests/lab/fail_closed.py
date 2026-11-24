"""With the voice service stopped, nobody gets in (run.sh)."""

import time

import pymumble_py3 as pm
from pymumble_py3.constants import PYMUMBLE_CONN_STATE_CONNECTED


def tryit(user, pw):
    m = pm.Mumble("lab-murmur", user, port=64738, password=pw, reconnect=False)
    m.start()
    time.sleep(4)
    ok = m.connected == PYMUMBLE_CONN_STATE_CONNECTED and m.users.myself is not None
    m.stop()
    return ok


print(
    ("PASS " if not tryit("Pilot", "good-token") else "FAIL ")
    + "voice service down: token holder refused"
)
print(
    ("PASS " if tryit("Insider", "labserverpw") else "FAIL ")
    + "only the secret server password gets in (keep it secret)"
)
