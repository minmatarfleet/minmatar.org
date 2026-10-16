from django.test import SimpleTestCase, TestCase

from intel.services.paste import (
    DSCAN,
    LOCAL,
    PasteError,
    detect_kind,
    parse,
)
from intel.services.ships import ship_list, summarize_dscan

DSCAN_PASTE = "\n".join(
    [
        "597\tPilot A's Punisher\tPunisher\t12,400 km",
        "597\tPilot B's Punisher\tPunisher\t12,410 km",
        "16236\tPilot C's Coercer\tCoercer\t12,380 km",
        "2006\tPilot D's Omen\tOmen\t12,520 km",
        "12003\tPilot E's Zealot\tZealot\t12,520 km",
        "670\tCapsule\tCapsule\t12,600 km",
        "35832\tSome Astrahus\tAstrahus\t3.2 AU",
        "99999999\tMystery\tFuture Hull\t-",
    ]
)

LOCAL_PASTE = "Ardo Kesh\nNyra Holdt\r\n  \nO'Brien Jr.\nardo kesh\n"


class DetectTests(SimpleTestCase):
    def test_dscan(self):
        self.assertEqual(detect_kind(DSCAN_PASTE), DSCAN)

    def test_local(self):
        self.assertEqual(detect_kind(LOCAL_PASTE), LOCAL)

    def test_neither(self):
        self.assertIsNone(detect_kind("hello there\twith a tab"))
        self.assertIsNone(detect_kind("   "))

    def test_local_dedupes_case_insensitively(self):
        kind, names = parse(LOCAL_PASTE)
        self.assertEqual(kind, LOCAL)
        self.assertEqual(names, ["Ardo Kesh", "Nyra Holdt", "O'Brien Jr."])

    def test_kind_override(self):
        with self.assertRaises(PasteError):
            parse(LOCAL_PASTE, DSCAN)

    def test_empty_and_huge(self):
        with self.assertRaises(PasteError):
            parse("")
        with self.assertRaises(PasteError):
            parse("Ardo Kesh\n" * 30_000)


class SummarizeDscanTests(TestCase):
    def test_classes_sizes_and_other(self):
        _, entries = parse(DSCAN_PASTE)
        summary = summarize_dscan(entries)

        self.assertEqual(summary["objects"], 8)
        self.assertEqual(summary["ships"], 5)
        self.assertEqual(summary["capsules"], 1)
        self.assertEqual(
            [c["name"] for c in summary["classes"]],
            ["Cruiser", "Destroyer", "Frigate"],
        )
        # Biggest first; the Zealot (HAC) outranks the T1 Omen.
        self.assertEqual(
            [h["name"] for h in summary["hulls"]],
            ["Zealot", "Omen", "Coercer", "Punisher"],
        )
        self.assertEqual(summary["hulls"][-1]["count"], 2)
        other = {row["name"]: row for row in summary["other_items"]}
        self.assertEqual(other["Astrahus"]["group"], "Structure")
        # Unknown to the fixture and eveuniverse: named from the paste.
        self.assertEqual(other["Future Hull"]["group"], "Other")

    def test_ship_list_from_feed_counts(self):
        ships = ship_list({"597": 3, "19720": 1, "670": 4, "bad": 2})
        self.assertEqual(
            [(s["name"], s["count"]) for s in ships],
            [("Revelation", 1), ("Punisher", 3)],
        )
