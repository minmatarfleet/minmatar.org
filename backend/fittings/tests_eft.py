"""
fittings.eft: the one EFT parser, and parity with the readers it replaced.

The ``_old_*`` functions are verbatim copies of the EFT readers that market,
fleets and fittings each kept before they moved onto fittings.eft. The
corpus tests run every fit in ``test_data/eft_corpus.json`` (the public
guide fits from the frontend) plus the edge-case fits below through old and
new and pin the differences to the intended ones:

* market now splits ``Module, Charge`` lines and strips ``/offline``; it
  used to keep the whole line as one unresolvable name and drop both items.
* fleets refit/supply helpers now strip ``/offline``.
* everything else is identical.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from django.test import SimpleTestCase

from fittings.eft import (
    EftItem,
    eft_item_names,
    fitted_modules,
    item_quantities,
    parse_eft_header,
    parse_eft_items,
    purchase_items,
    split_qty,
)
from fittings.models import EveFitting

CORPUS = json.loads(
    (Path(__file__).parent / "test_data" / "eft_corpus.json").read_text()
)

# Copied from the EVE client (Fitting window → Copy to clipboard): loaded
# charges after a comma, an offline module, drones and cargo.
CHARGED_EFT = """[Hurricane, Hurricane [FL33T]]
Gyrostabilizer II
Gyrostabilizer II
Damage Control II
[Empty Low slot]

50MN Quad LiF Restrained Microwarpdrive
Large Shield Extender II
Warp Disruptor II /offline

220mm Vulcan AutoCannon II, Republic Fleet EMP M
220mm Vulcan AutoCannon II, Republic Fleet EMP M
220mm Vulcan AutoCannon II, Republic Fleet EMP M
Heavy Missile Launcher II, Scourge Heavy Missile
Small Energy Neutralizer II

Medium Core Defense Field Extender I
Medium Core Defense Field Extender I
Medium Core Defense Field Extender I


Hammerhead II x5

Republic Fleet EMP M x2000
Scourge Heavy Missile x500
Nanite Repair Paste x50
"""

EDGE_CASES = [
    CHARGED_EFT,
    "[Hurricane, Cane [FL33T]]\nGyrostabilizer II\n",
    "[Rifter]\n200mm AutoCannon I, Republic Fleet EMP S\n",
    "[Rifter, CRLF]\r\nDamage Control I\r\n\r\nWarrior I x2\r\n",
    "[Rifter, Offline]\nStasis Webifier I /OFFLINE\nDamage Control I\n",
    "",
]

_OLD_HEADER_RE = re.compile(r"^\[(?P<ship>[^,\]]+)(?:,\s*(?P<name>.*))?\]$")
_OLD_FLEETS_QTY_SUFFIX_RE = re.compile(r"\s+x\d+$")
_OLD_OFFLINE_SUFFIX_RE = re.compile(r"\s*/offline$", re.IGNORECASE)
_OLD_REFITS_QTY_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)$")


def _old_market_parse_eft_items(eft_format):
    lines = eft_format.strip().split("\n")
    if not lines:
        return {}
    items = defaultdict(int)
    header = lines[0].strip()
    ship_name = header.split(",")[0].strip().strip("[]")
    if ship_name:
        items[ship_name] += 1
    cargo_re = re.compile(r"^(.+?)\s+x(\d+)$")
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("[Empty "):
            continue
        m = cargo_re.match(line)
        if m:
            items[m.group(1).strip()] += int(m.group(2))
        else:
            items[line] += 1
    return dict(items)


def _old_fleets_eft_item_names(eft_format):
    names = set()
    for raw in (eft_format or "").splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        line = _OLD_FLEETS_QTY_SUFFIX_RE.sub(
            "", _OLD_OFFLINE_SUFFIX_RE.sub("", line)
        )
        names.add(line.split(",", 1)[0].strip())
    names.discard("")
    return names


def _old_fleets_parse_eft_header(eft_format):
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return "", ""
    m = _OLD_HEADER_RE.match(lines[0].strip())
    if not m:
        return "", ""
    return m.group("ship").strip(), (m.group("name") or "").strip()


def _old_fleets_parse_eft_items(eft_format):
    items = []
    for raw in (eft_format or "").strip().splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        if _OLD_FLEETS_QTY_SUFFIX_RE.search(line):
            name, qty = split_qty(line)
            items.append(EftItem(name=name, quantity=qty, stacked=True))
            continue
        offline = bool(_OLD_OFFLINE_SUFFIX_RE.search(line))
        line = _OLD_OFFLINE_SUFFIX_RE.sub("", line)
        name, _, charge = line.partition(",")
        items.append(
            EftItem(
                name=name.strip(),
                charge=charge.strip() or None,
                offline=offline,
            )
        )
    return items


def _old_eft_fitted_modules(eft_format):
    counts = Counter()
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return counts
    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("[Empty "):
            continue
        if _OLD_REFITS_QTY_SUFFIX_RE.match(line):
            continue
        module = line.split(",", 1)[0].strip()
        if module:
            counts[module] += 1
    return counts


def _old_ship_name_from_eft(eft_format):
    first_line = eft_format.split("\n")[0]
    return first_line.split(",")[0].strip().strip("[]")


def _old_fitting_name_from_eft(eft_format):
    if not (eft_format and eft_format.strip()):
        return ""
    parts = eft_format.split("\n")[0].split(",", 1)
    if len(parts) < 2:
        return ""
    fitting_name = parts[1].strip()
    if fitting_name.endswith("]"):
        fitting_name = fitting_name[:-1].strip()
    return fitting_name


def _old_eft_purchase_items(eft_format):
    needed = Counter()
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return needed
    ship = _old_ship_name_from_eft(eft_format)
    if ship:
        needed[ship] += 1
    for raw in lines[1:]:
        line = raw.strip()
        if (
            not line
            or line.startswith("[Empty ")
            or _OLD_REFITS_QTY_SUFFIX_RE.match(line)
        ):
            continue
        module = line.split(",", 1)[0].strip()
        if module:
            needed[module] += 1
    return needed


def _has_charge_or_offline(eft_format):
    for raw in (eft_format or "").splitlines()[1:]:
        line = raw.strip()
        if _OLD_REFITS_QTY_SUFFIX_RE.match(line):
            continue
        if "," in line or _OLD_OFFLINE_SUFFIX_RE.search(line):
            return True
    return False


def _strip_offline(counter):
    out = Counter()
    for name, qty in counter.items():
        out[_OLD_OFFLINE_SUFFIX_RE.sub("", name)] += qty
    return out


def _all_fits():
    return [row["eft"] for row in CORPUS] + EDGE_CASES


class EftParserTestCase(SimpleTestCase):
    def test_client_export_with_charges(self):
        self.assertEqual(
            parse_eft_header(CHARGED_EFT), ("Hurricane", "Hurricane [FL33T]")
        )
        items = parse_eft_items(CHARGED_EFT)
        launcher = next(i for i in items if i.name.startswith("Heavy"))
        self.assertEqual(launcher.charge, "Scourge Heavy Missile")
        scram = next(i for i in items if i.name == "Warp Disruptor II")
        self.assertTrue(scram.offline)
        self.assertEqual(
            item_quantities(CHARGED_EFT),
            {
                "Hurricane": 1,
                "Gyrostabilizer II": 2,
                "Damage Control II": 1,
                "50MN Quad LiF Restrained Microwarpdrive": 1,
                "Large Shield Extender II": 1,
                "Warp Disruptor II": 1,
                "220mm Vulcan AutoCannon II": 3,
                "Heavy Missile Launcher II": 1,
                "Small Energy Neutralizer II": 1,
                "Medium Core Defense Field Extender I": 3,
                "Hammerhead II": 5,
                # 2000 in cargo + 1 loaded in each of three guns.
                "Republic Fleet EMP M": 2003,
                "Scourge Heavy Missile": 501,
                "Nanite Repair Paste": 50,
            },
        )

    def test_old_market_parser_dropped_charged_and_offline_modules(self):
        old = _old_market_parse_eft_items(CHARGED_EFT)
        self.assertNotIn("220mm Vulcan AutoCannon II", old)
        self.assertNotIn("Heavy Missile Launcher II", old)
        self.assertNotIn("Warp Disruptor II", old)
        self.assertIn("Warp Disruptor II /offline", old)

    def test_projections(self):
        self.assertEqual(
            fitted_modules(CHARGED_EFT)["220mm Vulcan AutoCannon II"], 3
        )
        self.assertNotIn("Hammerhead II", fitted_modules(CHARGED_EFT))
        self.assertNotIn("Republic Fleet EMP M", purchase_items(CHARGED_EFT))
        self.assertEqual(purchase_items(CHARGED_EFT)["Hurricane"], 1)
        self.assertIn("Hammerhead II", eft_item_names(CHARGED_EFT))
        self.assertNotIn(
            "Republic Fleet EMP M, x", eft_item_names(CHARGED_EFT)
        )

    def test_bracketed_fit_name_and_bad_header(self):
        self.assertEqual(
            parse_eft_header("[Hurricane, Cane [FL33T]]\n"),
            ("Hurricane", "Cane [FL33T]"),
        )
        self.assertEqual(parse_eft_header("[Rifter]"), ("Rifter", ""))
        self.assertEqual(parse_eft_header("Rifter, no brackets"), ("", ""))
        self.assertEqual(parse_eft_header(""), ("", ""))

    def test_empty_input(self):
        self.assertEqual(parse_eft_items(""), [])
        self.assertEqual(item_quantities(""), {})
        self.assertEqual(item_quantities(None), {})


class EftCorpusParityTestCase(SimpleTestCase):
    """Old readers vs fittings.eft on every corpus fit."""

    def test_corpus_is_loaded(self):
        self.assertGreaterEqual(len(CORPUS), 50)

    def test_fleets_parser_unchanged(self):
        for eft in _all_fits():
            with self.subTest(eft=eft[:40]):
                self.assertEqual(
                    parse_eft_header(eft), _old_fleets_parse_eft_header(eft)
                )
                self.assertEqual(
                    parse_eft_items(eft), _old_fleets_parse_eft_items(eft)
                )
                self.assertEqual(
                    eft_item_names(eft), _old_fleets_eft_item_names(eft)
                )

    def test_header_readers_unchanged(self):
        for eft in _all_fits():
            if not eft:
                continue
            with self.subTest(eft=eft[:40]):
                self.assertEqual(
                    EveFitting.ship_name_from_eft(eft),
                    _old_ship_name_from_eft(eft),
                )
                self.assertEqual(
                    EveFitting.fitting_name_from_eft(eft),
                    _old_fitting_name_from_eft(eft),
                )

    def test_fitted_and_purchase_only_strip_offline(self):
        for eft in _all_fits():
            with self.subTest(eft=eft[:40]):
                self.assertEqual(
                    fitted_modules(eft),
                    _strip_offline(_old_eft_fitted_modules(eft)),
                )
                self.assertEqual(
                    purchase_items(eft),
                    _strip_offline(_old_eft_purchase_items(eft)),
                )

    def test_market_quantities_only_add_what_was_dropped(self):
        for eft in _all_fits():
            old = _old_market_parse_eft_items(eft)
            new = item_quantities(eft)
            with self.subTest(eft=eft[:40]):
                if not _has_charge_or_offline(eft):
                    self.assertEqual(new, old)
                    continue
                # Lines the old parser kept whole are gone; every other
                # count can only grow, by the modules/charges it dropped.
                kept = {
                    name: qty
                    for name, qty in old.items()
                    if "," not in name
                    and not _OLD_OFFLINE_SUFFIX_RE.search(name)
                }
                for name, qty in kept.items():
                    self.assertGreaterEqual(new.get(name, 0), qty, name)
                added = Counter(new) - Counter(kept)
                dropped = Counter()
                for name, qty in old.items():
                    if name in kept:
                        continue
                    line = _OLD_OFFLINE_SUFFIX_RE.sub("", name)
                    module, _, charge = line.partition(",")
                    dropped[module.strip()] += qty
                    if charge.strip():
                        dropped[charge.strip()] += qty
                self.assertEqual(added, dropped)
