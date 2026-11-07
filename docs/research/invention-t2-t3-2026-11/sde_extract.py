"""Extract invention / T2 / T3 facts from CCP's JSONL SDE into one JSON file."""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAW = Path(sys.argv[1])
OUT = Path(sys.argv[2])


def load(name):
    out = {}
    with open(RAW / f"{name}.jsonl") as fh:
        for line in fh:
            d = json.loads(line)
            out[d["_key"]] = d
    return out


types = load("types")
groups = load("groups")
cats = load("categories")
bps = load("blueprints")
td = load("typeDogma")
metagroups = load("metaGroups")


def nm(t):
    return types[t]["name"]["en"] if t in types else str(t)


def grp(t):
    return types[t]["groupID"]


def gname(g):
    return groups[g]["name"]["en"]


def cat(t):
    return groups[grp(t)]["categoryID"]


def cname(c):
    return cats[c]["name"]["en"]


def attrs(t):
    return {a["attributeID"]: a["value"] for a in td.get(t, {}).get("dogmaAttributes", [])}


# product -> blueprint for manufacturing / reactions
made_by = {}
react_by = {}
for bid, bp in bps.items():
    acts = bp.get("activities", {})
    for p in acts.get("manufacturing", {}).get("products", []):
        made_by[p["typeID"]] = bid
    for p in acts.get("reaction", {}).get("products", []):
        react_by[p["typeID"]] = bid

encryption = {t for t in types if grp(t) == 270 and "Encryption" in nm(t)}

# ---------------------------------------------------------------- invention
inventions = []
for bid, bp in bps.items():
    inv = bp.get("activities", {}).get("invention")
    if not inv:
        continue
    src_is_relic = "Relic" in nm(bid) or cat(bid) != 9
    for p in inv.get("products", []):
        t2bp = p["typeID"]
        t2bp_bp = bps.get(t2bp, {})
        prod = None
        for pp in t2bp_bp.get("activities", {}).get("manufacturing", {}).get("products", []):
            prod = pp["typeID"]
        if prod is None or not types.get(prod, {}).get("published"):
            continue
        skills = inv.get("skills", [])
        enc = [s["typeID"] for s in skills if s["typeID"] in encryption]
        sci = [s["typeID"] for s in skills if s["typeID"] not in encryption]
        inventions.append(
            {
                "source": bid,
                "source_name": nm(bid),
                "relic": src_is_relic,
                "t2bp": t2bp,
                "product": prod,
                "product_name": nm(prod),
                "group": gname(grp(prod)),
                "category": cname(cat(prod)),
                "meta_group": types[prod].get("metaGroupID"),
                "probability": p.get("probability"),
                "runs": p.get("quantity"),
                "time": inv.get("time"),
                "materials": [(m["typeID"], m["quantity"]) for m in inv.get("materials", [])],
                "encryption": [nm(e) for e in enc],
                "science": [nm(s) for s in sci],
            }
        )

# probability by group
by_group = defaultdict(list)
for i in inventions:
    by_group[(i["category"], i["group"], i["relic"])].append(i)
group_rows = []
for (c, g, relic), items in sorted(by_group.items()):
    probs = Counter(round(x["probability"], 3) for x in items)
    runs = Counter(x["runs"] for x in items)
    dc = [sum(q for _, q in x["materials"] if nm(_).startswith("Datacore")) for x in items]
    group_rows.append(
        {
            "category": c,
            "group": g,
            "relic": relic,
            "count": len(items),
            "probability": dict(probs),
            "runs": dict(runs),
            "datacores_total_median": statistics.median(dc) if dc else 0,
            "time_median_s": statistics.median(x["time"] for x in items),
        }
    )

enc_counter = Counter(e for i in inventions for e in i["encryption"])
sci_counter = Counter(s for i in inventions for s in i["science"])

# ---------------------------------------------------------------- decryptors
dec = []
for t in types:
    if grp(t) in (1304, 979) and types[t].get("published"):
        a = attrs(t)
        dec.append(
            {
                "type": t,
                "name": nm(t),
                "group": gname(grp(t)),
                "prob_mult": a.get(1112),
                "me": a.get(1113),
                "te": a.get(1114),
                "runs": a.get(1124),
            }
        )

# ---------------------------------------------------------------- relics
relics = [i for i in inventions if i["relic"]]

# ---------------------------------------------------------------- BOM trees


def tree(t, qty=1.0, depth=0, maxdepth=6):
    """Base (ME0) material tree, per unit of t."""
    node = {"type": t, "name": nm(t), "qty": qty, "group": gname(grp(t))}
    if depth >= maxdepth:
        return node
    if t in made_by:
        bp = bps[made_by[t]]["activities"]["manufacturing"]
        per = bp["products"][0]["quantity"]
        node["via"] = "manufacturing"
        node["time"] = bp["time"]
        node["per_run"] = per
        node["children"] = [tree(m["typeID"], m["quantity"] / per, depth + 1) for m in bp.get("materials", [])]
    elif t in react_by:
        bp = bps[react_by[t]]["activities"]["reaction"]
        per = bp["products"][0]["quantity"]
        node["via"] = "reaction"
        node["formula"] = nm(react_by[t])
        node["time"] = bp["time"]
        node["per_run"] = per
        node["children"] = [tree(m["typeID"], m["quantity"] / per, depth + 1) for m in bp.get("materials", [])]
    return node


samples = [
    "Muninn", "Vagabond", "Sleipnir", "Claymore", "Scimitar", "Hound", "Jaguar", "Wolf", "Sabre",
    "Hyena", "Rapier", "Huginn", "Broadsword", "Panther", "Vargur", "Loki", "Svipul",
    "Gyrostabilizer II", "200mm AutoCannon II", "Medium Armor Repairer II", "Hobgoblin II",
    "Republic Fleet EMP S",
]
by_name = {nm(t): t for t in types if types[t].get("published")}
trees = {s: tree(by_name[s]) for s in samples if s in by_name}

# loki subsystems
loki_subs = [t for t in types if types[t].get("published") and nm(t).startswith("Loki ") and cat(t) == 32]
for t in loki_subs:
    trees[nm(t)] = tree(t)

# reaction formula summary
reactions = []
for bid, bp in bps.items():
    r = bp.get("activities", {}).get("reaction")
    if not r or not types.get(bid, {}).get("published"):
        continue
    p = r["products"][0]
    reactions.append(
        {
            "formula": nm(bid),
            "group": gname(grp(bid)),
            "product": nm(p["typeID"]),
            "product_group": gname(grp(p["typeID"])),
            "per_run": p["quantity"],
            "time": r["time"],
            "inputs": [(nm(m["typeID"]), m["quantity"]) for m in r.get("materials", [])],
        }
    )

# T2 product list for pricing (all invented items + materials one level down)
manuf = {}
for i in inventions:
    bp = bps[i["t2bp"]]["activities"]["manufacturing"]
    manuf[i["product"]] = {
        "t2bp": i["t2bp"],
        "per_run": bp["products"][0]["quantity"],
        "time": bp["time"],
        "materials": [(m["typeID"], m["quantity"]) for m in bp.get("materials", [])],
        "max_runs": bps[i["t2bp"]].get("maxProductionLimit"),
    }
# T1 product of source BPs (copy cost EIV)
t1 = {}
for i in inventions:
    if not i["relic"]:
        m = bps[i["source"]].get("activities", {}).get("manufacturing")
        if m and m.get("products"):
            t1[i["source"]] = {
                "product": m["products"][0]["typeID"],
                "materials": [(x["typeID"], x["quantity"]) for x in m.get("materials", [])],
                "copy_time": bps[i["source"]]["activities"].get("copying", {}).get("time"),
            }

names = {}
def addname(t):
    names[t] = nm(t)
for i in inventions:
    for t in (i["source"], i["t2bp"], i["product"]):
        addname(t)
    for t, _ in i["materials"]:
        addname(t)
for p, m in manuf.items():
    for t, _ in m["materials"]:
        addname(t)
for s, v in t1.items():
    addname(v["product"])
    for t, _ in v["materials"]:
        addname(t)
for d in dec:
    addname(d["type"])

product_meta = {
    p: {"group": gname(grp(p)), "category": cname(cat(p)), "group_id": grp(p), "category_id": cat(p),
        "volume": types[p].get("volume"), "market_group": types[p].get("marketGroupID")}
    for p in manuf
}

OUT.write_text(
    json.dumps(
        {
            "sde_build": json.loads((RAW / "_sde.jsonl").read_text().splitlines()[0]),
            "inventions": inventions,
            "group_rows": group_rows,
            "encryption_counts": enc_counter.most_common(),
            "science_counts": sci_counter.most_common(),
            "decryptors": dec,
            "relics": relics,
            "trees": trees,
            "reactions": reactions,
            "manuf": {str(k): v for k, v in manuf.items()},
            "t1": {str(k): v for k, v in t1.items()},
            "names": {str(k): v for k, v in names.items()},
            "product_meta": {str(k): v for k, v in product_meta.items()},
        },
        indent=1,
    )
)
print("inventions", len(inventions), "relic", len(relics), "decryptors", len(dec), "reactions", len(reactions))
