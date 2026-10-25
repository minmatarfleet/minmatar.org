"""Building a snapshot from CCP's JSONL layout."""

import json
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

from capabilities.engine import sde as sde_mod


def _write(directory: Path, name: str, rows: list[dict]):
    (directory / f"{name}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf8"
    )


def _ccp_files(directory: Path):
    _write(
        directory,
        "_sde",
        [{"_key": "sde", "buildNumber": 42, "releaseDate": "2026-10-23"}],
    )
    _write(
        directory,
        "groups",
        [
            {"_key": 25, "name": {"en": "Frigate"}, "categoryID": 6},
            {"_key": 255, "name": {"en": "Gunnery"}, "categoryID": 16},
            {"_key": 999, "name": {"en": "Asteroid"}, "categoryID": 25},
        ],
    )
    _write(
        directory,
        "types",
        [
            {
                "_key": 597,
                "name": {"en": "Punisher"},
                "groupID": 25,
                "published": True,
            },
            {
                "_key": 3300,
                "name": {"en": "Gunnery"},
                "groupID": 255,
                "published": True,
            },
            {
                "_key": 1230,
                "name": {"en": "Veldspar"},
                "groupID": 999,
                "published": True,
            },
            {
                "_key": 1373,
                "name": {"en": "Character"},
                "groupID": 1,
                "published": False,
            },
        ],
    )
    _write(
        directory,
        "typeDogma",
        [
            {
                "_key": 597,
                "dogmaAttributes": [
                    {"attributeID": 48, "value": 140.0},
                    {"attributeID": 182, "value": 3300.0},
                    {"attributeID": 277, "value": 1.0},
                ],
                "dogmaEffects": [{"effectID": 100, "isDefault": False}],
            }
        ],
    )
    _write(
        directory,
        "dogmaEffects",
        [
            {
                "_key": 100,
                "name": "testEffect",
                "effectCategoryID": 0,
                "modifierInfo": [
                    {
                        "domain": "shipID",
                        "func": "LocationRequiredSkillModifier",
                        "modifiedAttributeID": 64,
                        "modifyingAttributeID": 292,
                        "operation": 6,
                        "skillTypeID": 3300,
                    }
                ],
            },
            {"_key": 101, "name": "unused", "effectCategoryID": 0},
        ],
    )
    _write(
        directory,
        "dogmaAttributes",
        [
            {
                "_key": 48,
                "name": "cpuOutput",
                "defaultValue": 0,
                "stackable": True,
                "highIsGood": True,
            }
        ],
    )
    _write(
        directory,
        "certificates",
        [
            {
                "_key": 50,
                "name": {"en": "Small Energy Turret"},
                "skillTypes": [
                    {
                        "_key": 3300,
                        "basic": 1,
                        "standard": 2,
                        "improved": 3,
                        "advanced": 4,
                        "elite": 5,
                    }
                ],
            }
        ],
    )
    _write(
        directory,
        "masteries",
        [
            {
                "_key": 597,
                "_value": [
                    {"_key": 0, "_value": [50]},
                    {"_key": 4, "_value": [50]},
                ],
            }
        ],
    )
    _write(
        directory,
        "typeBonus",
        [
            {
                "_key": 597,
                "types": [
                    {
                        "_key": 3331,
                        "_value": [
                            {
                                "bonus": 5,
                                "bonusText": {
                                    "en": "bonus to armor resistances"
                                },
                                "importance": 1,
                            }
                        ],
                    }
                ],
            }
        ],
    )


class BuildSnapshotTest(SimpleTestCase):
    def test_from_a_zip_keeps_only_what_the_engine_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "files"
            directory.mkdir()
            _ccp_files(directory)
            path = Path(tmp) / "sde.zip"
            with zipfile.ZipFile(path, "w") as zf:
                for f in directory.iterdir():
                    zf.write(f, f.name)
            snapshot = sde_mod.build_snapshot(path)
        self.assertEqual(snapshot["build"], 42)
        self.assertIn(597, snapshot["types"])
        self.assertIn(1373, snapshot["types"])
        self.assertNotIn(1230, snapshot["types"])  # asteroids are not kept
        self.assertIn(100, snapshot["effects"])
        self.assertNotIn(101, snapshot["effects"])
        self.assertEqual(snapshot["effects"][100][2][0]["skillTypeID"], 3300)

        data = sde_mod.SdeData(sde_mod.unpack(sde_mod.pack(snapshot)))
        self.assertEqual(data.resolve("punisher"), 597)
        self.assertEqual(data.required_skills(597), {3300: 1})
        self.assertEqual(data.mastery_levels(597)[3300], (1, 1, 1, 1, 5))
        self.assertEqual(data.hull_traits(597)[3331][0][0], 5)
        mod = next(data.modifiers(597))[1]
        self.assertEqual(mod.skill, 3300)
