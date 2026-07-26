"""Tests for reference fixture export/load."""

import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group
from django.db.models import signals

from app.test import TestCase
from eveonline.models import EveLocation
from fittings.models import (
    DOCTRINE_TYPE_NON_STRATEGIC,
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
)
from fixtures.export import (
    collect_reference_data,
    serialize_bundle,
    write_fixture_files,
)
from fixtures.load import clear_reference_data, load_fixture_dir
from groups.models import AffiliationType
from tribes.models import Tribe, TribeGroup


class ExportSanitizationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )

    def test_tribe_discord_and_user_fields_nulled_in_serialized_output(self):
        group = Group.objects.create(name="Tribe Role")
        tribe = Tribe.objects.create(
            name="Capitals",
            slug="capitals",
            discord_channel_id=123456789012345678,
            group=group,
            chief=self.user,
        )
        TribeGroup.objects.create(
            tribe=tribe,
            name="Dreads",
            discord_channel_id=987654321098765432,
            group=group,
            chief=self.user,
        )

        bundle = collect_reference_data("default")
        serialized = serialize_bundle(bundle)
        tribes_rows = serialized["06_tribes.json"]

        tribe_rows = [r for r in tribes_rows if r["model"] == "tribes.tribe"]
        group_rows = [
            r for r in tribes_rows if r["model"] == "tribes.tribegroup"
        ]
        self.assertEqual(1, len(tribe_rows))
        self.assertEqual(1, len(group_rows))

        tribe_fields = tribe_rows[0]["fields"]
        self.assertIsNone(tribe_fields["discord_channel_id"])
        self.assertIsNone(tribe_fields["chief"])
        self.assertIsNone(tribe_fields["group"])

        tg_fields = group_rows[0]["fields"]
        self.assertIsNone(tg_fields["discord_channel_id"])
        self.assertIsNone(tg_fields["chief"])
        self.assertIsNone(tg_fields["group"])

    def test_affiliation_type_keeps_group_fk(self):
        group = Group.objects.create(name="Member")
        AffiliationType.objects.create(
            name="Member",
            group=group,
            priority=1,
            default=True,
        )

        bundle = collect_reference_data("default")
        serialized = serialize_bundle(bundle)
        aff_rows = serialized["03_affiliation_types.json"]
        self.assertEqual(1, len(aff_rows))
        self.assertEqual(group.pk, aff_rows[0]["fields"]["group"])


class ExportRoundTripTestCase(TestCase):
    def test_clear_preserves_fittings(self):
        fitting = EveFitting.objects.create(
            name="Test Fit",
            ship_id=587,
            description="desc",
            eft_format="[Rifter, Test Fit]\n\n",
        )
        loc = EveLocation.objects.create(
            location_id=9001,
            location_name="Staging",
            solar_system_id=3000,
            solar_system_name="Test System",
            short_name="STG",
            staging_active=True,
        )
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="doctrine",
        )
        doctrine.locations.add(loc)
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=fitting,
            role="primary",
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle = collect_reference_data("default")
            written = write_fixture_files(bundle, tmp_path)
            self.assertNotIn("04_fittings.json", written)
            self.assertIn("05_doctrines.json", written)

            clear_reference_data()
            self.assertEqual(1, EveFitting.objects.count())
            self.assertEqual(0, EveDoctrine.objects.count())

            # Doctrine fixture FKs still point at the preserved fitting.
            load_fixture_dir(tmp_path)
            self.assertEqual(1, EveFitting.objects.count())
            self.assertEqual(1, EveDoctrine.objects.count())
            loaded = EveDoctrine.objects.get(name="Test Doctrine")
            self.assertEqual(1, loaded.locations.count())
            self.assertEqual(
                1,
                EveDoctrineFitting.objects.filter(
                    doctrine=loaded, fitting__name="Test Fit"
                ).count(),
            )

    def test_write_fixture_files_omits_fittings(self):
        EveFitting.objects.create(
            name="Solo Fit",
            ship_id=587,
            description="",
            eft_format="[Rifter, Solo Fit]\n\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle = collect_reference_data("default")
            written = write_fixture_files(bundle, tmp_path)
            self.assertNotIn("04_fittings.json", written)
            self.assertNotIn("09_nvy_navy_destroyer_fittings.json", written)
            doctrines = json.loads(
                (tmp_path / "05_doctrines.json").read_text(encoding="utf-8")
            )
            self.assertIsInstance(doctrines, list)
