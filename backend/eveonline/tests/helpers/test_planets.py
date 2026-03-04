"""Tests for eveonline.helpers.characters.planets – update_character_planets."""

import factory
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType
from eveonline.client import EsiClient, EsiResponse
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterPlanet
from eveonline.helpers.characters.planets import (
    update_character_planets,
    _extract_planet_outputs_with_daily,
)

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


# ---------------------------------------------------------------------------
# Unit tests for _extract_planet_outputs_with_daily (supply-chain capping)
# ---------------------------------------------------------------------------


class ExtractPlanetOutputsSupplyCapTest(TestCase):
    """
    Tests for the supply-chain-limited factory output calculation.

    Planet topology used throughout:
      Extractor (pin 100) → Launchpad (pin 400) → Basic factory (pin 200) → Launchpad
    Schematic 126: cycle_time 1800 s, consumes 3000 P0 per cycle, produces 20 P1.
    """

    # Shared planet structure (pins without extractor_details for factory-only tests)
    LAUNCHPAD_PIN = {"pin_id": 400, "type_id": 2544}
    FACTORY_PIN = {"pin_id": 200, "type_id": 2473, "schematic_id": 126}

    SCHEMATIC_CYCLE = {126: 1800}

    def _planet(
        self, extractor_cycle, extractor_qty, include_storage_to_factory=True
    ):
        """
        Build a planet_detail dict with one extractor, one launchpad, one factory.

        extractor → launchpad (route qty = extractor_qty per extractor cycle)
        launchpad → factory (route qty = 3000 per factory cycle, the schematic input)
        factory → launchpad (route qty = 20 per factory cycle, the schematic output)
        """
        pins = [
            {
                "pin_id": 100,
                "extractor_details": {
                    "cycle_time": extractor_cycle,
                    "product_type_id": 2267,
                    "qty_per_cycle": extractor_qty,
                    "heads": [],
                },
            },
            self.LAUNCHPAD_PIN,
            self.FACTORY_PIN,
        ]
        routes = [
            # Extractor → launchpad
            {
                "route_id": 1,
                "source_pin_id": 100,
                "destination_pin_id": 400,
                "content_type_id": 2267,
                "quantity": extractor_qty,
            },
            # Factory → launchpad (output)
            {
                "route_id": 3,
                "source_pin_id": 200,
                "destination_pin_id": 400,
                "content_type_id": 2398,
                "quantity": 20,
            },
        ]
        if include_storage_to_factory:
            routes.insert(
                1,
                {
                    # Launchpad → factory (input requirement: 3000 P0 per 1800 s cycle)
                    "route_id": 2,
                    "source_pin_id": 400,
                    "destination_pin_id": 200,
                    "content_type_id": 2267,
                    "quantity": 3000,
                },
            )
        return {"pins": pins, "routes": routes}

    def test_factory_supply_limited_when_extractor_under_produces(self):
        """
        Extractor cycle is slower than needed → factory runs at half capacity.

        Extractor: 3000 qty / 3600 s cycle = 72,000 P0/day
        Factory at capacity: 3000 P0 needed per 1800 s cycle = 144,000 P0/day
        Limiting factor: 72,000 / 144,000 = 0.5
        Expected produced P1: (20/1800 * 86400) * 0.5 = 480/day
        """
        detail = self._planet(extractor_cycle=3600, extractor_qty=3000)
        harvested, produced = _extract_planet_outputs_with_daily(
            detail, self.SCHEMATIC_CYCLE
        )

        self.assertIn(2267, harvested)
        extractor_daily = Decimal(3000) / Decimal(3600) * Decimal(86400)
        self.assertEqual(harvested[2267], extractor_daily)

        capacity = Decimal(20) / Decimal(1800) * Decimal(86400)
        supply = Decimal(3000) / Decimal(3600) * Decimal(86400)
        required = Decimal(3000) / Decimal(1800) * Decimal(86400)
        expected = capacity * (supply / required)
        self.assertAlmostEqual(
            float(produced.get(2398, 0)), float(expected), places=4
        )

    def test_factory_at_full_capacity_when_supply_balanced(self):
        """
        Extractor exactly matches factory needs → no supply limit applied.

        Extractor: 3000 qty / 1800 s = 144,000 P0/day = factory's full requirement.
        Expected produced P1: 20/1800 * 86400 = 960/day (full capacity).
        """
        detail = self._planet(extractor_cycle=1800, extractor_qty=3000)
        _, produced = _extract_planet_outputs_with_daily(
            detail, self.SCHEMATIC_CYCLE
        )

        capacity = Decimal(20) / Decimal(1800) * Decimal(86400)
        self.assertAlmostEqual(
            float(produced.get(2398, 0)), float(capacity), places=4
        )

    def test_factory_uses_capacity_when_no_inbound_routes(self):
        """
        Factory has no inbound routes (simplified/old ESI data) → capacity fallback.
        """
        detail = self._planet(
            extractor_cycle=3600,
            extractor_qty=3000,
            include_storage_to_factory=False,
        )
        _, produced = _extract_planet_outputs_with_daily(
            detail, self.SCHEMATIC_CYCLE
        )

        capacity = Decimal(20) / Decimal(1800) * Decimal(86400)
        self.assertAlmostEqual(
            float(produced.get(2398, 0)), float(capacity), places=4
        )

    def test_import_planet_uses_capacity(self):
        """
        Factory fed only by an import launchpad (no in-planet extractor supply)
        → capacity fallback because supply is unmeasurable.
        """
        detail = {
            "pins": [self.LAUNCHPAD_PIN, self.FACTORY_PIN],
            "routes": [
                # Launchpad → factory: import-fed (launchpad has no in-planet supply)
                {
                    "route_id": 2,
                    "source_pin_id": 400,
                    "destination_pin_id": 200,
                    "content_type_id": 2267,
                    "quantity": 3000,
                },
                {
                    "route_id": 3,
                    "source_pin_id": 200,
                    "destination_pin_id": 400,
                    "content_type_id": 2398,
                    "quantity": 20,
                },
            ],
        }
        _, produced = _extract_planet_outputs_with_daily(
            detail, self.SCHEMATIC_CYCLE
        )

        capacity = Decimal(20) / Decimal(1800) * Decimal(86400)
        self.assertAlmostEqual(
            float(produced.get(2398, 0)), float(capacity), places=4
        )
        # No harvested either — pure factory planet
        harvested, _ = _extract_planet_outputs_with_daily(
            detail, self.SCHEMATIC_CYCLE
        )
        self.assertEqual(harvested, {})

    def test_multi_tier_chain_propagates_supply_limit(self):
        """
        Two-tier chain: extractor → storage → basic factory → storage → advanced factory.
        Supply limit cascades: advanced factory is constrained by basic factory output,
        which is itself constrained by the extractor.

        Extractor: 3000 / 3600 s = 72,000 P0/day
        Basic factory (schematic 126, 1800 s): needs 3000/1800*86400=144,000 P0/day
          → factor 0.5 → produces 20/1800*86400*0.5 = 480 P1/day
        Advanced factory (schematic 127, 3600 s): needs 40/3600*86400=960 P1/day
          → supply 480 → factor 0.5 → produces 5/3600*86400*0.5 = 60 P2/day
        """
        detail = {
            "pins": [
                {
                    "pin_id": 100,
                    "extractor_details": {
                        "cycle_time": 3600,
                        "product_type_id": 2267,
                        "qty_per_cycle": 3000,
                        "heads": [],
                    },
                },
                {"pin_id": 400, "type_id": 2544},  # launchpad
                {"pin_id": 200, "type_id": 2473, "schematic_id": 126},  # basic
                {
                    "pin_id": 300,
                    "type_id": 2474,
                    "schematic_id": 127,
                },  # advanced
            ],
            "routes": [
                # Extractor → launchpad
                {
                    "route_id": 1,
                    "source_pin_id": 100,
                    "destination_pin_id": 400,
                    "content_type_id": 2267,
                    "quantity": 3000,
                },
                # Launchpad → basic factory
                {
                    "route_id": 2,
                    "source_pin_id": 400,
                    "destination_pin_id": 200,
                    "content_type_id": 2267,
                    "quantity": 3000,
                },
                # Basic factory → launchpad (P1)
                {
                    "route_id": 3,
                    "source_pin_id": 200,
                    "destination_pin_id": 400,
                    "content_type_id": 2398,
                    "quantity": 20,
                },
                # Launchpad → advanced factory (P1 input; needs 40/3600s cycle)
                {
                    "route_id": 4,
                    "source_pin_id": 400,
                    "destination_pin_id": 300,
                    "content_type_id": 2398,
                    "quantity": 40,
                },
                # Advanced factory → launchpad (P2)
                {
                    "route_id": 5,
                    "source_pin_id": 300,
                    "destination_pin_id": 400,
                    "content_type_id": 2399,
                    "quantity": 5,
                },
            ],
        }
        schematics = {126: 1800, 127: 3600}
        _, produced = _extract_planet_outputs_with_daily(detail, schematics)

        # Basic factory: 960 capacity * 0.5 = 480 P1/day
        self.assertAlmostEqual(float(produced.get(2398, 0)), 480.0, places=2)
        # Advanced factory: 120 capacity * 0.5 = 60 P2/day
        self.assertAlmostEqual(float(produced.get(2399, 0)), 60.0, places=2)
