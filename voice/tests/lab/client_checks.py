"""Lab checks against a real Murmur: run through run.sh."""

import json
import subprocess
import sys
import time

import redis
import pymumble_py3 as pm
from pymumble_py3.constants import (
    PYMUMBLE_CONN_STATE_CONNECTED,
    PYMUMBLE_CONN_STATE_FAILED,
)

r = redis.Redis(host="lab-redis", db=3)


def rec(ident, char, name, placement, commander=False, admitted=True, banned=False):
    groups = ["fleet"] + (["commanders", "capitals"] if commander else [])
    return {
        "version": 1,
        "character_id": char,
        "identity_id": ident,
        "display_name": name,
        "admitted": admitted,
        "banned": banned,
        "reason": "ok" if admitted else "banned",
        "server_groups": ["community"] if admitted else [],
        "branches": (
            {
                "1": {
                    "fleet_id": 501,
                    "lease_id": 601,
                    "groups": groups,
                    "placement": placement,
                    "commander": commander,
                    "part_of_fleet": True,
                }
            }
            if admitted
            else {}
        ),
        "preferred_branch": 1 if admitted else None,
    }


r.set(
    "voice:leases",
    json.dumps({"1": {"lease_id": 601, "fleet_id": 501, "wing_channels": {}}}),
)
for ident, char, name, placement, cmd, adm, ban in (
    (7, 9001, "[FL33T] O'Neil Logi", "Logistics", False, True, False),
    (8, 9002, "[FL33T] Lab FC", "Command", True, True, False),
    (9, 9003, "Banned Pilot", "Mainline", False, False, True),
):
    r.set(
        f"voice:char:{char}",
        json.dumps(rec(ident, char, name, placement, cmd, adm, ban)),
    )
    r.set(f"voice:identity:{ident}", str(char))
r.publish("voice:changed", "leases")


def make_cert(name):
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            f"/CN={name}",
            "-keyout",
            f"/tmp/{name}.key",
            "-out",
            f"/tmp/{name}.pem",
        ],
        check=True,
        capture_output=True,
    )
    return f"/tmp/{name}.pem", f"/tmp/{name}.key"


def connect(user, password="", cert=None, wait=6):
    kw = {}
    if cert:
        kw = {"certfile": cert[0], "keyfile": cert[1]}
    m = pm.Mumble(
        "lab-murmur", user, port=64738, password=password, reconnect=False, **kw
    )
    m.start()
    end = time.time() + wait
    while time.time() < end and m.connected not in (
        PYMUMBLE_CONN_STATE_CONNECTED,
        PYMUMBLE_CONN_STATE_FAILED,
    ):
        time.sleep(0.2)
    ok = m.connected == PYMUMBLE_CONN_STATE_CONNECTED and m.users.myself is not None
    return m, ok


def channel_name(m):
    time.sleep(7)  # one reconcile tick
    me = m.users.myself
    return m.channels[me["channel_id"]]["name"]


results = {}
m, ok = connect("Nobody")
results["no credentials refused"] = not ok
m.stop()
m, ok = connect("SuperUser", "labsu")
results["SuperUser refused"] = not ok
m.stop()
m, ok = connect("Banned", "banned-token")
results["banned refused"] = not ok
m.stop()
m, ok = connect("O'Neil Logi", "good-token")
results["token, no certificate: accepted"] = ok
if ok:
    results["placed in Logistics"] = channel_name(m) == "Logistics"
    results["display name set"] = m.users.myself["name"] == "[FL33T] O'Neil Logi"
m.stop()
time.sleep(1)
results["empty cert hash never bound"] = r.get("voice:cert:") is None
cert = make_cert("logi")
m, ok = connect("O'Neil Logi", "good-token-2", cert)
results["token binds certificate"] = ok
m.stop()
time.sleep(1)
m, ok = connect("Someone Else", "", cert)
results["bound certificate alone gets in"] = ok
if ok:
    results["certificate decides identity"] = (
        m.users.myself["name"] == "[FL33T] O'Neil Logi"
    )
m.stop()
m, ok = connect("Replay", "good-token")
results["spent token refused"] = not ok
m.stop()
for k, v in results.items():
    print(("PASS " if v else "FAIL ") + k)
sys.exit(0 if all(results.values()) else 1)
