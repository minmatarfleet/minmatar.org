"""Value added at each step of the T2/T3 supply chain, at Jita prices.

For every reaction formula and every component that feeds an invented item,
compare the Jita value of the output with the Jita cost of its inputs after
Amamake/Tatara bonuses. Also fetches The Forge market history for a doctrine list.
"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

S = Path(sys.argv[1])
RAW = S / "sde/raw"
jita = json.loads((S / "market/jita.json").read_text())
adjusted = {p["type_id"]: p.get("adjusted_price", 0.0) for p in json.loads((S / "market/prices.json").read_text())}
systems = {s["solar_system_id"]: {c["activity"]: c["cost_index"] for c in s["cost_indices"]}
           for s in json.loads((S / "market/systems.json").read_text())}
AMA = systems[30002537]
UA = {"User-Agent": "minmatar.org industry research"}


def load(name):
    out = {}
    with open(RAW / f"{name}.jsonl") as fh:
        for line in fh:
            d = json.loads(line)
            out[d["_key"]] = d
    return out


types = load("types")
groups = load("groups")
bps = load("blueprints")
nm = lambda t: types[t]["name"]["en"]
gname = lambda t: groups[types[t]["groupID"]]["name"]["en"]

# fetch any missing prices for chain types
need = set()
for bid, bp in bps.items():
    for act in ("reaction",):
        a = bp.get("activities", {}).get(act)
        if a and types.get(bid, {}).get("published"):
            need |= {m["typeID"] for m in a.get("materials", [])} | {p["typeID"] for p in a.get("products", [])}
model = json.loads((S / "out/model.json").read_text())
sde = json.loads((S / "out/sde.json").read_text())
component_ids = set()
for r in model["best_by_product"]:
    for t, _ in sde["manuf"][str(r["product"])]["materials"]:
        component_ids.add(t)
made_by = {}
for bid, bp in bps.items():
    for p in bp.get("activities", {}).get("manufacturing", {}).get("products", []):
        made_by[p["typeID"]] = bid
comp_bp = {}
for t in component_ids:
    if t in made_by and gname(t) in ("Construction Components", "Hybrid Tech Components"):
        comp_bp[t] = made_by[t]
        need.add(t)
        need |= {m["typeID"] for m in bps[made_by[t]]["activities"]["manufacturing"].get("materials", [])}
missing = sorted(t for t in need if str(t) not in jita)
for i in range(0, len(missing), 180):
    chunk = missing[i:i + 180]
    url = "https://market.fuzzwork.co.uk/aggregates/?station=60003760&types=" + ",".join(map(str, chunk))
    jita.update(json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)))
    time.sleep(0.5)
(S / "market/jita.json").write_text(json.dumps(jita))


def px(t, side="sell"):
    j = jita.get(str(t))
    if not j:
        return None
    v = float(j[side]["percentile"])
    return v if v > 0 else None


def qty(runs, base, me):
    if base == 1:
        return runs
    return max(runs, math.ceil(round(runs * base * (1 - me), 2)))


def job(value, sci, bonus):
    return value * sci * (1 - bonus) * 0.5 + value * (0.0075 + 0.04)


# Reactions at the Amamake Tatara: L Reactor Efficiency II (lowsec x1.0 => 2.4% ME), no Tatara ME role.
REACT_ME = 0.024
reactions = []
for bid, bp in bps.items():
    a = bp.get("activities", {}).get("reaction")
    if not a or not types.get(bid, {}).get("published"):
        continue
    runs = 100  # a realistic batch; ME rounding matters at 1 run
    prod = a["products"][0]
    out_val = px(prod["typeID"])
    if out_val is None:
        continue
    cost = 0.0
    cost_buy = 0.0
    ok = True
    for m in a.get("materials", []):
        p = px(m["typeID"])
        if p is None:
            ok = False
            break
        n = qty(runs, m["quantity"], REACT_ME)
        cost += n * p
        cost_buy += n * (px(m["typeID"], "buy") or p)
    if not ok:
        continue
    eiv = sum(m["quantity"] * adjusted.get(m["typeID"], 0) for m in a["materials"]) * runs
    jc = job(eiv, AMA["reaction"], 0.0)
    value = prod["quantity"] * runs * out_val
    reactions.append({
        "formula": nm(bid), "group": gname(bid), "product": nm(prod["typeID"]), "product_group": gname(prod["typeID"]),
        "hours_per_run": a["time"] / 3600, "value_per_run": value / runs,
        "input_cost_per_run": (cost + jc) / runs, "margin": (value - cost - jc) / value,
        "margin_buy_inputs": (value - cost_buy - jc) / value,
        "profit_per_hour_one_slot": (value - cost - jc) / runs / (a["time"] / 3600 * 0.75 * 0.8),
    })

# Components at the Sotiyo: 1% role + 3.8% Thukker XL rig
COMP_ME = 1 - (1 - 0.01) * (1 - 0.038)
components = []
for t, bid in comp_bp.items():
    a = bps[bid]["activities"]["manufacturing"]
    runs = 100
    per = a["products"][0]["quantity"]
    out_val = px(t)
    if out_val is None:
        continue
    cost = 0.0
    ok = True
    for m in a.get("materials", []):
        p = px(m["typeID"])
        if p is None:
            ok = False
            break
        cost += qty(runs, m["quantity"], COMP_ME) * p
    if not ok:
        continue
    eiv = sum(m["quantity"] * adjusted.get(m["typeID"], 0) for m in a["materials"]) * runs
    jc = job(eiv, AMA["manufacturing"], 0.05)
    value = out_val * per * runs
    components.append({"component": nm(t), "group": gname(t), "value": out_val,
                       "input_cost": (cost + jc) / (per * runs), "margin": (value - cost - jc) / value,
                       "inputs": [nm(m["typeID"]) for m in a["materials"]]})

# Market history (The Forge) for doctrine-relevant products
watch = ["Muninn", "Vagabond", "Sleipnir", "Claymore", "Scimitar", "Hound", "Jaguar", "Wolf", "Sabre", "Hyena",
         "Rapier", "Huginn", "Broadsword", "Panther", "Vargur", "Loki", "Svipul", "Gyrostabilizer II",
         "200mm AutoCannon II", "Medium Armor Repairer II", "Hobgoblin II", "Damage Control II",
         "Large Shield Extender II", "Warp Scrambler II", "Stasis Webifier II", "Warrior II",
         "Multispectrum Energized Membrane II", "10MN Afterburner II", "50MN Microwarpdrive II",
         "1600mm Steel Plates II", "Medium Trimark Armor Pump II", "Hail S", "Barrage M",
         "425mm AutoCannon II", "720mm Howitzer Artillery II", "Heavy Assault Missile Launcher II",
         "Ballistic Control System II", "Nanofiber Internal Structure II", "Medium Shield Extender II"]
by_name = {nm(t): t for t in types if types[t].get("published") and types[t]["groupID"] not in (0,)}
history = {}
for n in watch:
    t = by_name.get(n)
    if not t:
        continue
    url = f"https://esi.evetech.net/latest/markets/10000002/history/?datasource=tranquility&type_id={t}"
    try:
        h = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
    except Exception as exc:  # noqa: BLE001
        print("history fail", n, exc)
        continue
    last30 = h[-30:]
    last90 = h[-90:]
    history[n] = {
        "type": t,
        "vol30": sum(x["volume"] for x in last30) / 30,
        "avg30": sum(x["average"] * x["volume"] for x in last30) / max(1, sum(x["volume"] for x in last30)),
        "avg90": sum(x["average"] * x["volume"] for x in last90) / max(1, sum(x["volume"] for x in last90)),
        "first": h[0]["date"] if h else None,
    }
    time.sleep(0.2)

(S / "out/chain.json").write_text(json.dumps({"reactions": reactions, "components": components, "history": history}, indent=1))
print("reactions", len(reactions), "components", len(components), "history", len(history))
