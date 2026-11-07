"""Price every T2/T3 invention line as it would run at the Amamake Sotiyo.

Inputs: out/sde.json (sde_extract.py), market/prices.json (ESI adjusted),
market/jita.json (Fuzzwork Jita 4-4 aggregates), market/systems.json (ESI indices).
"""
import json
import math
import sys
from pathlib import Path

S = Path(sys.argv[1])
d = json.loads((S / "out/sde.json").read_text())
adjusted = {p["type_id"]: p.get("adjusted_price", 0.0) for p in json.loads((S / "market/prices.json").read_text())}
jita = json.loads((S / "market/jita.json").read_text())
systems = {s["solar_system_id"]: {c["activity"]: c["cost_index"] for c in s["cost_indices"]}
           for s in json.loads((S / "market/systems.json").read_text())}
names = {int(k): v for k, v in d["names"].items()}
meta = {int(k): v for k, v in d["product_meta"].items()}

AMAMAKE = 30002537
SCI_MFG = systems[AMAMAKE]["manufacturing"]
SCI_INV = systems[AMAMAKE]["invention"]
SCI_COPY = systems[AMAMAKE]["copying"]
FW_BONUS = -0.5          # FW infrastructure level 5, cost-index gross only
FAC_TAX = 0.0075         # corp facility tax (facility_profiles.py)
SCC = 0.04
SOTIYO_COST = 0.05
SOTIYO_ME = 0.01
LAB_RIG_COST = 0.10 * 1.9   # XL Laboratory Optimization I, lowsec x1.9
XL_RIG_ME = 0.02 * 1.9      # XL Ship / Thukker component rigs, lowsec x1.9
SALES_TAX = 0.075 * (1 - 0.11 * 5)  # Accounting V
BROKER = 0.015               # Broker Relations V, no standings
SELL_FEES = SALES_TAX + BROKER
SKILL_MULT = 1 + (5 + 5) / 30 + 4 / 40   # Science V/V, Encryption IV


def sell(t):
    j = jita.get(str(t))
    if not j:
        return None
    v = float(j["sell"]["percentile"])
    return v if v > 0 else None


def buy(t):
    j = jita.get(str(t))
    if not j:
        return None
    v = float(j["buy"]["percentile"])
    return v if v > 0 else None


def adj(t):
    return adjusted.get(int(t), 0.0)


def eiv(materials, runs=1):
    return sum(q * adj(t) for t, q in materials) * runs


def job_cost(value, sci, struct_bonus, fw=FW_BONUS):
    return value * sci * (1 - struct_bonus) * (1 + fw) + value * (FAC_TAX + SCC)


def qty(runs, base, me):
    if base == 1:
        return runs
    return max(runs, math.ceil(round(runs * base * (1 - me), 2)))


SHIP_CATS = {"Ship", "Subsystem"}
decryptors = [x for x in d["decryptors"] if x["group"] == "Generic Decryptor"]
options = [{"name": "None", "type": None, "prob_mult": 1.0, "me": 0, "te": 0, "runs": 0}] + decryptors

rows = []
missing = 0
for inv in d["inventions"]:
    prod = inv["product"]
    m = d["manuf"][str(prod)]
    pm = meta[prod]
    price = sell(prod)
    if price is None:
        missing += 1
        continue
    rig_me = XL_RIG_ME if pm["category"] in SHIP_CATS else 0.0
    product_eiv = eiv(m["materials"])  # per run
    inv_job = job_cost(0.02 * product_eiv, SCI_INV, 1 - (1 - SOTIYO_COST) * (1 - LAB_RIG_COST))
    dc_cost = 0.0
    dc_ok = True
    for t, q in inv["materials"]:
        p = sell(t)
        if p is None:
            dc_ok = False
            p = 0
        dc_cost += p * q
    if inv["relic"]:
        src_cost = sell(inv["source"]) or 0  # the relic itself is consumed
        copy_cost = 0.0
    else:
        src_cost = 0.0
        t1 = d["t1"].get(str(inv["source"]))
        copy_cost = job_cost(0.02 * eiv(t1["materials"]), SCI_COPY, 1 - (1 - SOTIYO_COST) * (1 - LAB_RIG_COST)) if t1 else 0.0
    best = None
    per_option = []
    for opt in options:
        if inv["relic"] and opt["type"] is None:
            pass
        dec_price = sell(opt["type"]) if opt["type"] else 0.0
        if opt["type"] and dec_price is None:
            continue
        p = min(1.0, inv["probability"] * SKILL_MULT * opt["prob_mult"])
        runs = inv["runs"] + int(opt["runs"])
        # Invention output is ME 2 / TE 4 before decryptors (T3 assumed the same).
        me = (2 + opt["me"]) / 100
        attempt = dc_cost + dec_price + inv_job + copy_cost + src_cost
        inv_per_unit = attempt / p / (runs * m["per_run"])
        me_total = 1 - (1 - me) * (1 - SOTIYO_ME) * (1 - rig_me)
        mat_cost = 0.0
        mat_cost_buy = 0.0
        ok = True
        for t, q in m["materials"]:
            pr = sell(t)
            if pr is None:
                ok = False
                break
            n = qty(runs, q, me_total)
            mat_cost += n * pr
            mat_cost_buy += n * (buy(t) or pr)
        if not ok:
            continue
        mfg_job = job_cost(product_eiv * runs, SCI_MFG, SOTIYO_COST)
        build_per_unit = (mat_cost + mfg_job) / (runs * m["per_run"])
        unit = inv_per_unit + build_per_unit
        unit_buy = inv_per_unit + (mat_cost_buy + mfg_job) / (runs * m["per_run"])
        r = {
            "unit_cost_buyorders": unit_buy, "mfg_job_per_unit": mfg_job / (runs * m["per_run"]),
            "decryptor": opt["name"], "p": p, "runs": runs, "me": me, "inv_per_unit": inv_per_unit,
            "build_per_unit": build_per_unit, "unit_cost": unit,
        }
        per_option.append(r)
        if best is None or unit < best["unit_cost"]:
            best = r
    if best is None:
        missing += 1
        continue
    none = next((o for o in per_option if o["decryptor"] == "None"), None)
    net = price * (1 - SELL_FEES)
    rows.append({
        "product": prod, "name": inv["product_name"], "group": inv["group"], "category": inv["category"],
        "relic": inv["relic"], "source": inv["source_name"], "base_p": inv["probability"], "base_runs": inv["runs"],
        "jita_sell": price, "jita_buy": buy(prod), "net_sale": net, "best": best, "none": none,
        "profit": net - best["unit_cost"], "margin": (net - best["unit_cost"]) / net,
        "margin_buyorders": (net - best["unit_cost_buyorders"]) / net,
        "inv_share": best["inv_per_unit"] / best["unit_cost"], "dc_ok": dc_ok,
        "encryption": inv["encryption"],
        "product_eiv": product_eiv,
        "options": per_option,
    })

# collapse duplicates (relic grades / alt T1 sources): keep best per product but remember all
by_prod = {}
for r in rows:
    k = r["product"]
    if k not in by_prod or r["best"]["unit_cost"] < by_prod[k]["best"]["unit_cost"]:
        by_prod[k] = r

out = {
    "assumptions": {
        "system": "Amamake", "sci_mfg": SCI_MFG, "sci_inv": SCI_INV, "sci_copy": SCI_COPY,
        "fw_bonus": FW_BONUS, "facility_tax": FAC_TAX, "scc": SCC, "sotiyo_cost": SOTIYO_COST,
        "sotiyo_me": SOTIYO_ME, "lab_rig_cost": LAB_RIG_COST, "xl_rig_me": XL_RIG_ME,
        "sell_fees": SELL_FEES, "skill_mult": SKILL_MULT,
    },
    "rows": rows,
    "best_by_product": list(by_prod.values()),
    "missing": missing,
}
(S / "out/model.json").write_text(json.dumps(out, indent=1))
print("rows", len(rows), "products", len(by_prod), "missing", missing)
