"""
Regenerate tests/fixtures/sde_subset.json.gz from a CCP JSONL zip:

    python -m capabilities.tests.make_fixture <eve-online-static-data-*-jsonl.zip>

The subset keeps every skill plus the types in the fixture fits, so the
golden tests run the real dogma offline.
"""

import gzip
import json
import sys
from pathlib import Path

from capabilities.engine import sde as sde_mod
from fittings.eft import parse_eft_header, parse_eft_items

FIXTURES = Path(__file__).parent / "fixtures"
EXTRA_TYPES = (
    "Medium Remote Armor Repairer I",
    "Large Remote Armor Repairer I",
)


def subset(snapshot: dict, names: set[str]) -> dict:
    data = sde_mod.SdeData(snapshot)
    keep = {sde_mod.CHARACTER_TYPE_ID}
    for name in names:
        tid = data.resolve(name)
        if tid:
            keep.add(tid)
    keep |= {
        t
        for t, (_, g) in data.types.items()
        if data.groups[g][1] == sde_mod.CAT_SKILL
    }
    effects = {e for t in keep for e in data.effect_ids(t)}
    groups = {data.group_id(t) for t in keep}
    certs = {
        c
        for t in keep
        for ids in data.masteries.get(t, {}).values()
        for c in ids
    }
    return {
        "build": snapshot["build"],
        "release_date": snapshot["release_date"],
        "groups": {g: v for g, v in snapshot["groups"].items() if g in groups},
        "types": {t: v for t, v in snapshot["types"].items() if t in keep},
        "type_attrs": {
            t: v for t, v in snapshot["type_attrs"].items() if t in keep
        },
        "type_effects": {
            t: v for t, v in snapshot["type_effects"].items() if t in keep
        },
        "effects": {
            e: v for e, v in snapshot["effects"].items() if e in effects
        },
        "attributes": snapshot["attributes"],
        "certificates": {
            c: v for c, v in snapshot["certificates"].items() if c in certs
        },
        "masteries": {
            t: v for t, v in snapshot["masteries"].items() if t in keep
        },
        "traits": {t: v for t, v in snapshot["traits"].items() if t in keep},
    }


def fixture_names() -> set[str]:
    names = set(EXTRA_TYPES)
    for path in FIXTURES.glob("*.eft"):
        eft = path.read_text()
        names.add(parse_eft_header(eft)[0])
        for item in parse_eft_items(eft):
            names.add(item.name)
            if item.charge:
                names.add(item.charge)
    return names


def main(zip_path: str):
    snapshot = subset(sde_mod.build_snapshot(zip_path), fixture_names())
    with gzip.open(
        FIXTURES / "sde_subset.json.gz", "wt", encoding="utf8"
    ) as fh:
        json.dump(snapshot, fh, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1])
