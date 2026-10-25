"""
The slice of CCP's static data export (SDE) the capability engine reads.

ESI (and so django-eveuniverse) leaves out three things the engine needs:
the ``skillTypeID`` on effect modifiers (which skill a bonus applies to),
ship masteries with their certificates, and hull traits. CCP publishes the
full SDE as JSONL at developers.eveonline.com; ``build_snapshot`` keeps the
part we use, small enough to store as one compressed row.

Pure Python: no Django imports, so the prototype and tests can use it
directly.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
import zlib
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

LATEST_URL = (
    "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
)
ZIP_URL = (
    "https://developers.eveonline.com/static-data/tranquility/"
    "eve-online-static-data-{build}-jsonl.zip"
)

CAT_SHIP = 6
CAT_MODULE = 7
CAT_CHARGE = 8
CAT_SKILL = 16
CAT_DRONE = 18
CAT_IMPLANT = 20
CAT_SUBSYSTEM = 32
CAT_FIGHTER = 87
KEPT_CATEGORIES = frozenset(
    {
        CAT_SHIP,
        CAT_MODULE,
        CAT_CHARGE,
        CAT_SKILL,
        CAT_DRONE,
        CAT_IMPLANT,
        CAT_SUBSYSTEM,
        CAT_FIGHTER,
    }
)
# The pilot: maxActiveDrones and other character attributes live on it.
CHARACTER_TYPE_ID = 1373

# requiredSkill1..6 and their levels.
REQUIRED_SKILL_ATTRS = (
    (182, 277),
    (183, 278),
    (184, 279),
    (1285, 1286),
    (1289, 1287),
    (1290, 1288),
)
ATTR_SKILL_LEVEL = 280
ATTR_SKILL_RANK = 275
CERT_LEVELS = ("basic", "standard", "improved", "advanced", "elite")


def _rows(lines):
    for line in lines:
        line = line.strip()
        if line:
            yield json.loads(line)


class _Source:
    """Reads ``<name>.jsonl`` from a CCP zip or an unpacked directory."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def rows(self, name: str):
        filename = f"{name}.jsonl"
        if not self.path.is_file():
            with open(self.path / filename, encoding="utf8") as fh:
                yield from _rows(fh)
            return
        with zipfile.ZipFile(self.path) as zf:
            member = next(
                (n for n in zf.namelist() if n.rsplit("/", 1)[-1] == filename),
                None,
            )
            if member is None:
                raise FileNotFoundError(f"{filename} not in {self.path}")
            with zf.open(member) as raw:
                yield from _rows(io.TextIOWrapper(raw, encoding="utf8"))


def _en(value) -> str:
    if isinstance(value, dict):
        return value.get("en", "")
    return value or ""


def build_snapshot(path: str | Path) -> dict:
    """Extract the engine's slice from a CCP JSONL zip or directory."""
    src = _Source(path)
    meta = next(src.rows("_sde"))
    groups = {
        g["_key"]: [_en(g.get("name")), g["categoryID"]]
        for g in src.rows("groups")
    }
    types = {}
    for t in src.rows("types"):
        group = groups.get(t["groupID"])
        if t["_key"] == CHARACTER_TYPE_ID or (
            group and group[1] in KEPT_CATEGORIES and t.get("published")
        ):
            types[t["_key"]] = [_en(t.get("name")), t["groupID"]]
    type_attrs, type_effects = {}, {}
    for d in src.rows("typeDogma"):
        if d["_key"] not in types:
            continue
        type_attrs[d["_key"]] = {
            a["attributeID"]: a["value"] for a in d.get("dogmaAttributes", [])
        }
        type_effects[d["_key"]] = [
            e["effectID"] for e in d.get("dogmaEffects", [])
        ]
    used_effects = {e for effects in type_effects.values() for e in effects}
    effects = {
        e["_key"]: [
            e.get("name", ""),
            e.get("effectCategoryID", 0),
            e.get("modifierInfo", []),
        ]
        for e in src.rows("dogmaEffects")
        if e["_key"] in used_effects
    }
    attributes = {
        a["_key"]: [
            a.get("name", ""),
            a.get("defaultValue", 0.0),
            bool(a.get("stackable", True)),
            bool(a.get("highIsGood", True)),
        ]
        for a in src.rows("dogmaAttributes")
    }
    certificates = {
        c["_key"]: [
            _en(c.get("name")),
            {
                s["_key"]: [s.get(level, 0) for level in CERT_LEVELS]
                for s in c.get("skillTypes", [])
            },
        ]
        for c in src.rows("certificates")
    }
    masteries = {
        m["_key"]: {lv["_key"]: lv["_value"] for lv in m["_value"]}
        for m in src.rows("masteries")
        if m["_key"] in types
    }
    traits = {}
    for b in src.rows("typeBonus"):
        if b["_key"] not in types:
            continue
        per_skill = {}
        for t in b.get("types", []):
            per_skill[t["_key"]] = [
                [
                    x.get("bonus", 0),
                    _en(x.get("bonusText")),
                    x.get("importance", 9),
                ]
                for x in t["_value"]
            ]
        if per_skill:
            traits[b["_key"]] = per_skill
    used_groups = {t[1] for t in types.values()}
    return {
        "build": meta["buildNumber"],
        "release_date": meta.get("releaseDate", ""),
        "groups": {k: v for k, v in groups.items() if k in used_groups},
        "types": types,
        "type_attrs": type_attrs,
        "type_effects": type_effects,
        "effects": effects,
        "attributes": attributes,
        "certificates": certificates,
        "masteries": masteries,
        "traits": traits,
    }


def pack(snapshot: dict) -> bytes:
    return zlib.compress(
        json.dumps(snapshot, separators=(",", ":")).encode(), 6
    )


def int_keys(value):
    if isinstance(value, dict):
        return {
            (
                int(k) if isinstance(k, str) and k.lstrip("-").isdigit() else k
            ): int_keys(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [int_keys(v) for v in value]
    return value


def unpack(blob: bytes) -> dict:
    return int_keys(json.loads(zlib.decompress(blob)))


@dataclass(frozen=True)
class Modifier:
    func: str
    domain: str
    modified: int
    modifying: int
    operation: int
    skill: int | None = None
    group: int | None = None


class SdeData:
    """Read helpers over one snapshot."""

    def __init__(self, snapshot: dict):
        self.raw = snapshot
        self.build = snapshot["build"]
        self.types = snapshot["types"]
        self.groups = snapshot["groups"]
        self._attrs = snapshot["type_attrs"]
        self._effects = snapshot["type_effects"]
        self.effects = snapshot["effects"]
        self.attributes = snapshot["attributes"]
        self.certificates = snapshot["certificates"]
        self.masteries = snapshot["masteries"]
        self.traits = snapshot["traits"]

    @cached_property
    def by_name(self) -> dict[str, int]:
        out = {}
        for tid, (name, _) in self.types.items():
            if name:
                out.setdefault(name.lower(), tid)
        return out

    def resolve(self, name: str) -> int | None:
        return self.by_name.get(re.sub(r"\s+", " ", name.strip()).lower())

    def name(self, tid: int) -> str:
        t = self.types.get(tid)
        return t[0] if t else f"#{tid}"

    def group_id(self, tid: int) -> int | None:
        t = self.types.get(tid)
        return t[1] if t else None

    def group_name(self, tid: int) -> str:
        g = self.groups.get(self.group_id(tid))
        return g[0] if g else ""

    def category(self, tid: int) -> int | None:
        g = self.groups.get(self.group_id(tid))
        return g[1] if g else None

    def attrs(self, tid: int) -> dict[int, float]:
        return self._attrs.get(tid, {})

    def attr_name(self, aid: int) -> str:
        a = self.attributes.get(aid)
        return a[0] if a else f"attr{aid}"

    def attr_default(self, aid: int) -> float:
        a = self.attributes.get(aid)
        return float(a[1]) if a else 0.0

    def attr_stackable(self, aid: int) -> bool:
        a = self.attributes.get(aid)
        return a[2] if a else True

    def effect_ids(self, tid: int) -> list[int]:
        return self._effects.get(tid, [])

    def effect_category(self, eid: int) -> int:
        e = self.effects.get(eid)
        return e[1] if e else 0

    def modifiers(self, tid: int, categories=None):
        """(effect id, Modifier) for every modifier on a type's effects."""
        for eid in self.effect_ids(tid):
            e = self.effects.get(eid)
            if not e:
                continue
            if categories is not None and e[1] not in categories:
                continue
            for m in e[2]:
                if (
                    "modifiedAttributeID" not in m
                    or "modifyingAttributeID" not in m
                ):
                    continue
                yield eid, Modifier(
                    func=m.get("func", ""),
                    domain=m.get("domain", ""),
                    modified=m["modifiedAttributeID"],
                    modifying=m["modifyingAttributeID"],
                    operation=m.get("operation", 0),
                    skill=m.get("skillTypeID"),
                    group=m.get("groupID"),
                )

    def required_skills(self, tid: int) -> dict[int, int]:
        a = self.attrs(tid)
        out = {}
        for skill_attr, level_attr in REQUIRED_SKILL_ATTRS:
            skill = int(a.get(skill_attr, 0) or 0)
            if skill > 0:
                out[skill] = max(
                    out.get(skill, 0), int(a.get(level_attr, 0) or 0)
                )
        return out

    def with_prerequisites(self, reqs: dict[int, int]) -> dict[int, int]:
        out = dict(reqs)
        stack = list(reqs)
        while stack:
            for pre, level in self.required_skills(stack.pop()).items():
                if out.get(pre, 0) < level:
                    out[pre] = level
                    stack.append(pre)
        return out

    def skill_rank(self, skill: int) -> float:
        return float(self.attrs(skill).get(ATTR_SKILL_RANK, 1.0) or 1.0)

    def mastery_levels(self, hull: int) -> dict[int, tuple[int, ...]]:
        """{skill: (level at mastery I..V)}, cumulative across levels."""
        out: dict[int, list[int]] = {}
        for m_level, cert_ids in self.masteries.get(hull, {}).items():
            for cid in cert_ids:
                cert = self.certificates.get(cid)
                if not cert:
                    continue
                for skill, levels in cert[1].items():
                    row = out.setdefault(skill, [0] * 5)
                    row[m_level] = max(row[m_level], levels[m_level])
        result = {}
        for skill, levels in out.items():
            run, acc = 0, []
            for x in levels:
                run = max(run, x)
                acc.append(run)
            result[skill] = tuple(acc)
        return result

    def hull_traits(self, hull: int) -> dict[int, list]:
        """{skill: [[bonus, text, importance], ...]}, headline bonus first."""
        return {
            skill: sorted(bonuses, key=lambda b: b[2])
            for skill, bonuses in self.traits.get(hull, {}).items()
            if skill > 0
        }
