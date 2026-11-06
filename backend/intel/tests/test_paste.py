from django.test import SimpleTestCase, TestCase

from intel.services.paste import (
    DSCAN,
    LOCAL,
    PasteError,
    detect_kind,
    parse,
    parse_distance_km,
)
from intel.services.ships import ship_list, summarize_dscan
from intel.services.system_from_scan import system_from_scan

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


class DistanceTests(SimpleTestCase):
    def test_locales_and_units(self):

        self.assertEqual(parse_distance_km("11,204 km"), 11204)
        self.assertEqual(parse_distance_km("11.204 km"), 11204)
        self.assertEqual(parse_distance_km("11 204 km"), 11204)
        self.assertEqual(parse_distance_km("11 204 km"), 11204)
        self.assertEqual(parse_distance_km("850 m"), 0.85)
        self.assertAlmostEqual(
            parse_distance_km("2.4 AU"), 2.4 * 149_597_870.7
        )
        self.assertAlmostEqual(
            parse_distance_km("2,4 AU"), 2.4 * 149_597_870.7
        )
        self.assertIsNone(parse_distance_km("-"))
        self.assertIsNone(parse_distance_km(""))

    def test_lines_keep_their_distance(self):
        _, entries = parse(DSCAN_PASTE)
        self.assertEqual(entries[0].distance_km, 12400)
        self.assertIsNone(entries[-1].distance_km)


GRID_PASTE = "\n".join(
    [
        "597\tPunisher one\tPunisher\t8,200 km",
        "597\tPunisher two\tPunisher\t1,450,000 km",
        "2006\tOmen\tOmen\t9,999 km",
        "2006\tFar Omen\tOmen\t3.1 AU",
        "12003\tZealot\tZealot\t-",
    ]
)


class OnGridTests(TestCase):
    def test_on_grid_counts(self):
        _, entries = parse(GRID_PASTE)
        summary = summarize_dscan(entries)
        self.assertTrue(summary["has_distances"])
        self.assertEqual(summary["on_grid_ships"], 2)
        hulls = {hull["name"]: hull for hull in summary["hulls"]}
        self.assertEqual(hulls["Punisher"]["on_grid"], 1)
        self.assertEqual(hulls["Omen"]["on_grid"], 1)
        # No distance printed: counted, never on grid.
        self.assertEqual(hulls["Zealot"]["count"], 1)
        self.assertEqual(hulls["Zealot"]["on_grid"], 0)
        self.assertEqual(hulls["Zealot"]["group"], "Heavy Assault Cruiser")
        self.assertEqual(hulls["Punisher"]["group"], "Frigate")
        classes = {c["name"]: c for c in summary["classes"]}
        self.assertEqual(sum(c["on_grid"] for c in classes.values()), 2)


class SystemFromScanTests(TestCase):
    def system(self, lines):

        _, entries = parse("\n".join(lines))
        return system_from_scan(entries)

    def test_celestial_names(self):
        self.assertEqual(
            self.system(
                [
                    "597\tPunisher\tPunisher\t8,200 km",
                    "14\tAmamake VII - Moon 3\tMoon\t4.8 AU",
                    "11\tAmamake II\tPlanet (Temperate)\t9.1 AU",
                    "6\tAmamake - Star\tSun G5 (Yellow)\t12.0 AU",
                ]
            ),
            (30002537, "Amamake"),
        )

    def test_customs_office_names_its_planet(self):
        self.assertEqual(
            self.system(
                ["2233\tCustoms Office (Amamake VII)\tCustoms Office\t1 AU"]
            ),
            (30002537, "Amamake"),
        )

    def test_gates_alone(self):
        self.assertEqual(
            self.system(
                [
                    "597\tPunisher\tPunisher\t8,200 km",
                ]
                + [
                    f"29624\tStargate ({name})\tStargate (Minmatar System)\t1 AU"
                    for name in (
                        "Osoggur",
                        "Gulmorogod",
                        "Vard",
                        "Siseide",
                        "Dal",
                        "Auga",
                    )
                ]
            ),
            (30002537, "Amamake"),
        )

    def test_gates_that_fit_two_systems_say_nothing(self):
        # Amamake and Siseide both link to Vard, Dal and Auga.
        # (Gates out of d-scan range leave this ambiguous more often.)
        self.assertIsNone(
            self.system(
                [
                    "29624\tStargate (Vard)\tStargate (Minmatar System)\t1 AU",
                    "29624\tStargate (Dal)\tStargate (Minmatar System)\t2 AU",
                    "29624\tStargate (Auga)\tStargate (Minmatar System)\t3 AU",
                ]
            )
        )

    def test_ships_only_says_nothing(self):
        self.assertIsNone(self.system(["597\tPunisher\tPunisher\t8 km"]))
