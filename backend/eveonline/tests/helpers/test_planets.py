"""Tests for eveonline.helpers.characters.planets – update_character_planets."""

import factory
from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType
from eveonline.client import EsiClient, EsiResponse
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterPlanet
from eveonline.helpers.characters.planets import update_character_planets


PLANETS_LIST = [
    {
        "last_update": "2026-02-16T02:59:23Z",
        "num_pins": 9,
        "owner_id": 5001,
        "planet_id": 40001,
        "planet_type": "barren",
        "solar_system_id": 30001,
        "upgrade_level": 4,
    },
    {
        "last_update": "2026-02-16T02:59:30Z",
        "num_pins": 6,
        "owner_id": 5001,
        "planet_id": 40002,
        "planet_type": "temperate",
        "solar_system_id": 30001,
        "upgrade_level": 3,
    },
]

PLANET_DETAIL_40001 = {
    "links": [],
    "pins": [
        {
            "pin_id": 100,
            "type_id": 2848,
            "extractor_details": {
                "cycle_time": 7200,
                "product_type_id": 2267,
                "qty_per_cycle": 7000,
                "heads": [{"head_id": 0, "latitude": 1.0, "longitude": 0.5}],
            },
            "latitude": 0.95,
            "longitude": 0.75,
        },
        {
            "pin_id": 101,
            "type_id": 2848,
            "extractor_details": {
                "cycle_time": 7200,
                "product_type_id": 2270,
                "qty_per_cycle": 6000,
                "heads": [{"head_id": 0, "latitude": 0.8, "longitude": 0.6}],
            },
            "latitude": 0.93,
            "longitude": 0.73,
        },
        {
            "pin_id": 200,
            "type_id": 2473,
            "schematic_id": 126,
            "latitude": 0.94,
            "longitude": 0.75,
        },
        {
            "pin_id": 201,
            "type_id": 2473,
            "schematic_id": 127,
            "latitude": 0.94,
            "longitude": 0.72,
        },
        {
            "pin_id": 300,
            "type_id": 2474,
            "schematic_id": 73,
            "latitude": 0.92,
            "longitude": 0.74,
        },
        {
            "pin_id": 400,
            "type_id": 2544,
            "latitude": 0.94,
            "longitude": 0.74,
        },
    ],
    "routes": [
        {
            "route_id": 1,
            "source_pin_id": 100,
            "destination_pin_id": 400,
            "content_type_id": 2267,
            "quantity": 3000,
            "waypoints": [],
        },
        {
            "route_id": 2,
            "source_pin_id": 101,
            "destination_pin_id": 400,
            "content_type_id": 2270,
            "quantity": 3000,
            "waypoints": [],
        },
        {
            "route_id": 3,
            "source_pin_id": 200,
            "destination_pin_id": 400,
            "content_type_id": 2398,
            "quantity": 20,
            "waypoints": [],
        },
        {
            "route_id": 4,
            "source_pin_id": 201,
            "destination_pin_id": 400,
            "content_type_id": 2399,
            "quantity": 20,
            "waypoints": [],
        },
        {
            "route_id": 5,
            "source_pin_id": 300,
            "destination_pin_id": 400,
            "content_type_id": 3689,
            "quantity": 5,
            "waypoints": [],
        },
    ],
}

PLANET_DETAIL_40002 = {
    "links": [],
    "pins": [
        {
            "pin_id": 500,
            "type_id": 2848,
            "extractor_details": {
                "cycle_time": 7200,
                "product_type_id": 2268,
                "qty_per_cycle": 5000,
                "heads": [{"head_id": 0, "latitude": 0.5, "longitude": 0.3}],
            },
            "latitude": 0.50,
            "longitude": 0.30,
        },
        {
            "pin_id": 600,
            "type_id": 2473,
            "schematic_id": 121,
            "latitude": 0.51,
            "longitude": 0.31,
        },
    ],
    "routes": [
        {
            "route_id": 10,
            "source_pin_id": 600,
            "destination_pin_id": 500,
            "content_type_id": 2393,
            "quantity": 20,
            "waypoints": [],
        },
    ],
}


def _ensure_eve_types(type_ids):
    """Create minimal EveCategory + EveGroup + EveType records for testing."""
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=9999,
        defaults={
            "name": "Test Category",
            "last_updated": now,
            "published": True,
        },
    )
    group, _ = EveGroup.objects.get_or_create(
        id=9999,
        defaults={
            "name": "Test Group",
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    created = {}
    for tid in type_ids:
        eve_type, _ = EveType.objects.get_or_create(
            id=tid,
            defaults={
                "name": f"Type {tid}",
                "last_updated": now,
                "eve_group": group,
                "published": True,
            },
        )
        created[tid] = eve_type
    return created


class UpdateCharacterPlanetsTest(TestCase):
    """Tests for the update_character_planets helper."""

    def setUp(self):
        super().setUp()
        all_type_ids = {2267, 2270, 2398, 2399, 3689, 2268, 2393}
        self.eve_types = _ensure_eve_types(all_type_ids)

    def _patch_get_or_create_esi(self):
        """Patch EveType.objects.get_or_create_esi to return our test records."""
        original = EveType.objects.get_or_create_esi

        def fake_get_or_create_esi(*args, **kwargs):
            type_id = kwargs.get("id") or (args[0] if args else None)
            if type_id is not None and type_id in self.eve_types:
                return self.eve_types[type_id], False
            return original(*args, **kwargs)

        return patch.object(
            type(EveType.objects),
            "get_or_create_esi",
            side_effect=fake_get_or_create_esi,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_creates_planets_and_outputs(self, esi_mock_cls):
        char = EveCharacter.objects.create(
            character_id=5001,
            character_name="PI Tester",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi

        esi.get_character_planets.return_value = EsiResponse(
            response_code=0, data=PLANETS_LIST
        )
        esi.get_character_planet_details.side_effect = lambda pid: (
            EsiResponse(response_code=0, data=PLANET_DETAIL_40001)
            if pid == 40001
            else EsiResponse(response_code=0, data=PLANET_DETAIL_40002)
        )

        with self._patch_get_or_create_esi():
            count = update_character_planets(5001)

        self.assertEqual(count, 2)
        self.assertEqual(
            EveCharacterPlanet.objects.filter(character=char).count(), 2
        )

        p1 = EveCharacterPlanet.objects.get(character=char, planet_id=40001)
        self.assertEqual(p1.planet_type, "barren")
        self.assertEqual(p1.solar_system_id, 30001)
        self.assertEqual(p1.upgrade_level, 4)
        self.assertEqual(p1.num_pins, 9)

        # Planet 40001: 2 harvested (2267, 2270) + 3 produced (2398, 2399, 3689)
        self.assertEqual(p1.outputs.filter(output_type="harvested").count(), 2)
        self.assertEqual(p1.outputs.filter(output_type="produced").count(), 3)

        harvested_ids = set(
            p1.outputs.filter(output_type="harvested").values_list(
                "eve_type_id", flat=True
            )
        )
        self.assertEqual(harvested_ids, {2267, 2270})

        produced_ids = set(
            p1.outputs.filter(output_type="produced").values_list(
                "eve_type_id", flat=True
            )
        )
        self.assertEqual(produced_ids, {2398, 2399, 3689})

        # Planet 40002: 1 harvested (2268) + 1 produced (2393)
        p2 = EveCharacterPlanet.objects.get(character=char, planet_id=40002)
        self.assertEqual(p2.outputs.filter(output_type="harvested").count(), 1)
        self.assertEqual(p2.outputs.filter(output_type="produced").count(), 1)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_removes_stale_planets(self, esi_mock_cls):
        """Planets no longer in ESI are deleted."""
        char = EveCharacter.objects.create(
            character_id=5002,
            character_name="PI Tester 2",
        )

        stale = EveCharacterPlanet.objects.create(
            character=char,
            planet_id=99999,
            planet_type="lava",
            solar_system_id=30099,
            upgrade_level=2,
            num_pins=3,
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi

        esi.get_character_planets.return_value = EsiResponse(
            response_code=0,
            data=[PLANETS_LIST[0]],
        )
        esi.get_character_planet_details.return_value = EsiResponse(
            response_code=0, data=PLANET_DETAIL_40001
        )

        with self._patch_get_or_create_esi():
            count = update_character_planets(5002)

        self.assertEqual(count, 1)
        self.assertFalse(
            EveCharacterPlanet.objects.filter(pk=stale.pk).exists()
        )
        self.assertTrue(
            EveCharacterPlanet.objects.filter(
                character=char, planet_id=40001
            ).exists()
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_skips_suspended_character(self, esi_mock_cls):
        EveCharacter.objects.create(
            character_id=5003,
            character_name="Suspended PI",
            esi_suspended=True,
        )

        count = update_character_planets(5003)

        self.assertEqual(count, 0)
        esi_mock_cls.assert_not_called()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_handles_failed_planets_list(self, esi_mock_cls):
        EveCharacter.objects.create(
            character_id=5004,
            character_name="PI No Token",
        )
        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi

        esi.get_character_planets.return_value = EsiResponse(response_code=905)

        count = update_character_planets(5004)

        self.assertEqual(count, 0)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_handles_failed_planet_detail(self, esi_mock_cls):
        """If a planet detail fetch fails, the planet is still created but with no outputs."""
        char = EveCharacter.objects.create(
            character_id=5005,
            character_name="PI Partial",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi

        esi.get_character_planets.return_value = EsiResponse(
            response_code=0,
            data=[PLANETS_LIST[0]],
        )
        esi.get_character_planet_details.return_value = EsiResponse(
            response_code=500
        )

        count = update_character_planets(5005)

        self.assertEqual(count, 1)
        planet = EveCharacterPlanet.objects.get(
            character=char, planet_id=40001
        )
        self.assertEqual(planet.outputs.count(), 0)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.planets.EsiClient")
    def test_idempotent_update(self, esi_mock_cls):
        """Running update twice with the same data produces the same result."""
        char = EveCharacter.objects.create(
            character_id=5006,
            character_name="PI Idempotent",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi

        esi.get_character_planets.return_value = EsiResponse(
            response_code=0,
            data=[PLANETS_LIST[0]],
        )
        esi.get_character_planet_details.return_value = EsiResponse(
            response_code=0, data=PLANET_DETAIL_40001
        )

        with self._patch_get_or_create_esi():
            update_character_planets(5006)
            update_character_planets(5006)

        self.assertEqual(
            EveCharacterPlanet.objects.filter(character=char).count(), 1
        )
        planet = EveCharacterPlanet.objects.get(
            character=char, planet_id=40001
        )
        self.assertEqual(planet.outputs.count(), 5)
