"""Download the inputs the other scripts read, into WORKDIR.

    python fetch_inputs.py WORKDIR
    python sde_extract.py WORKDIR/sde/raw WORKDIR/out/sde.json
    python fetch_inputs.py WORKDIR --jita      # needs out/sde.json for the type list
    python model.py WORKDIR && python chain.py WORKDIR && python integrated.py WORKDIR

Layout: WORKDIR/sde/raw/*.jsonl, WORKDIR/market/{prices,systems,jita}.json, WORKDIR/out/.
"""
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

W = Path(sys.argv[1])
UA = {"User-Agent": "minmatar.org industry research"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read()


(W / "market").mkdir(parents=True, exist_ok=True)
(W / "out").mkdir(parents=True, exist_ok=True)

if "--jita" not in sys.argv:
    build = json.loads(get("https://developers.eveonline.com/static-data/tranquility/latest.jsonl"))["buildNumber"]
    blob = get(f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{build}-jsonl.zip")
    zipfile.ZipFile(io.BytesIO(blob)).extractall(W / "sde/raw")
    (W / "market/prices.json").write_bytes(get("https://esi.evetech.net/latest/markets/prices/?datasource=tranquility"))
    (W / "market/systems.json").write_bytes(get("https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"))
    print("SDE build", build)
    sys.exit(0)

d = json.loads((W / "out/sde.json").read_text())
ids = set()
for i in d["inventions"]:
    ids |= {i["source"], i["product"]} | {t for t, _ in i["materials"]}
for p, m in d["manuf"].items():
    ids.add(int(p))
    ids |= {t for t, _ in m["materials"]}
for v in d["t1"].values():
    ids.add(v["product"])
ids |= {x["type"] for x in d["decryptors"]}
ids = sorted(ids)
out = {}
for i in range(0, len(ids), 180):
    chunk = ",".join(map(str, ids[i:i + 180]))
    out.update(json.loads(get(f"https://market.fuzzwork.co.uk/aggregates/?station=60003760&types={chunk}")))
    time.sleep(0.5)
(W / "market/jita.json").write_text(json.dumps(out))
print("priced", len(out))
