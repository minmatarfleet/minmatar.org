"""Re-price ship/module lines with components built in-house from Jita-priced inputs."""
import json, math, sys
from pathlib import Path
S = Path(sys.argv[1])
model = json.loads((S/"out/model.json").read_text())
sde = json.loads((S/"out/sde.json").read_text())
chain = json.loads((S/"out/chain.json").read_text())
jita = json.loads((S/"market/jita.json").read_text())
names = {int(k): v for k, v in sde["names"].items()}
comp_cost = {c["component"]: c["input_cost"] for c in chain["components"]}
def sell(t):
    j = jita.get(str(t)); v = float(j["sell"]["percentile"]) if j else 0
    return v or None
def qty(runs, base, me):
    return runs if base == 1 else max(runs, math.ceil(round(runs*base*(1-me), 2)))
out = []
for r in model["best_by_product"]:
    m = sde["manuf"][str(r["product"])]
    b = r["best"]
    ship = r["category"] in ("Ship", "Subsystem")
    me_total = 1 - (1 - b["me"]) * (1 - 0.01) * (1 - (0.038 if ship else 0))
    retail = 0.0; built = 0.0; comp_share = 0.0
    for t, q in m["materials"]:
        n = qty(b["runs"], q, me_total)
        p = sell(t) or 0
        retail += n * p
        nmn = names.get(t, str(t))
        c = comp_cost.get(nmn)
        if c is not None and c < p:
            built += n * c; comp_share += n * p
        else:
            built += n * p
    per = b["runs"] * m["per_run"]
    saving = (retail - built) / per
    unit_int = b["unit_cost"] - saving
    out.append({"name": r["name"], "category": r["category"], "group": r["group"], "relic": r["relic"],
                "margin_retail": r["margin"], "margin_integrated": (r["net_sale"] - unit_int) / r["net_sale"],
                "margin_buyorders": r["margin_buyorders"], "component_share": comp_share / retail if retail else 0})
(S/"out/integrated.json").write_text(json.dumps(out, indent=1))
import statistics
for c in ("Ship", "Module", "Charge", "Subsystem"):
    xs = [o for o in out if o["category"] == c]
    print(c, len(xs), "retail", round(statistics.median(o["margin_retail"] for o in xs), 3),
          "buy-orders", round(statistics.median(o["margin_buyorders"] for o in xs), 3),
          "integrated", round(statistics.median(o["margin_integrated"] for o in xs), 3),
          "profitable retail/integ", round(sum(o["margin_retail"] > 0 for o in xs)/len(xs), 2), round(sum(o["margin_integrated"] > 0 for o in xs)/len(xs), 2))
want = ["Muninn","Vagabond","Sleipnir","Claymore","Scimitar","Hound","Jaguar","Wolf","Sabre","Hyena","Rapier","Huginn","Broadsword","Panther","Vargur","Loki","Svipul"]
for o in out:
    if o["name"] in want:
        print(f"{o['name']:12s} retail {o['margin_retail']*100:6.1f}%  buyorders {o['margin_buyorders']*100:6.1f}%  integrated {o['margin_integrated']*100:6.1f}%")
