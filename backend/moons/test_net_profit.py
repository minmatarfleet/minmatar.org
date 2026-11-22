from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache

from app.test import TestCase
from moons.metenox import (
    CURSOR_KEY,
    parse_moon_name,
    sync_metenox_kills,
)
from moons.models import EveMoon, EveMoonDistribution, MetenoxKill
from moons.profit import profit_breakdown
from moons.tasks import update_moon_revenues

PRICES = {
    "Hydrocarbons": Decimal("400"),
    "Pyerite": Decimal("17"),
    "Mexallon": Decimal("60"),
    "Magmatic Gas": Decimal("2100"),
    "Nitrogen Fuel Block": Decimal("17460"),
    "Helium Fuel Block": Decimal("18530"),
}


class ProfitBreakdownTests(TestCase):
    def distributions(self):
        return [SimpleNamespace(ore="Bitumens", yield_percent=Decimal("0.5"))]

    def test_net_is_output_minus_a_month_of_fuel(self):
        breakdown = profit_breakdown(self.distributions(), PRICES)
        # 0.5 × 12 portions/h × (65×400 + 6000×17 + 400×60) × 24 × 30
        self.assertEqual(breakdown["revenue"], 656_640_000)
        fuel = {line["name"]: line for line in breakdown["fuel"]}
        # 200 gas and 5 blocks an hour, the cheapest block.
        self.assertEqual(fuel["Magmatic Gas"]["units"], 144_000)
        self.assertEqual(fuel["Magmatic Gas"]["isk"], 302_400_000)
        self.assertEqual(fuel["Nitrogen Fuel Block"]["units"], 3_600)
        self.assertNotIn("Helium Fuel Block", fuel)
        self.assertEqual(breakdown["fuel_cost"], 365_256_000)
        self.assertEqual(breakdown["net"], 656_640_000 - 365_256_000)
        names = [line["name"] for line in breakdown["output"]]
        self.assertEqual(names, ["Pyerite", "Hydrocarbons", "Mexallon"])

    def test_unpriced_fuel_leaves_net_unknown(self):
        prices = {k: v for k, v in PRICES.items() if k != "Magmatic Gas"}
        breakdown = profit_breakdown(self.distributions(), prices)
        self.assertEqual(breakdown["fuel"], [])
        self.assertIsNone(breakdown["net"])

    def test_unpriced_product_gives_nothing(self):
        prices = {k: v for k, v in PRICES.items() if k != "Pyerite"}
        self.assertIsNone(profit_breakdown(self.distributions(), prices))

    @patch("moons.tasks.get_prices", return_value=PRICES)
    def test_revenue_task_stores_net_and_lines(self, _):
        moon = EveMoon.objects.create(system="Jita", planet="IV", moon=4)
        EveMoonDistribution.objects.create(
            moon=moon, ore="Bitumens", yield_percent=Decimal("0.5")
        )
        update_moon_revenues()
        moon.refresh_from_db()
        self.assertEqual(moon.monthly_revenue, 656_640_000)
        self.assertEqual(moon.monthly_net, 656_640_000 - 365_256_000)
        self.assertEqual(len(moon.profit["output"]), 3)
        self.assertEqual(len(moon.profit["fuel"]), 2)
        self.assertIn("priced_at", moon.profit)

    @patch("moons.tasks.get_prices")
    def test_revenue_task_keeps_net_when_fuel_unpriced(self, get_prices):
        get_prices.return_value = {
            k: v for k, v in PRICES.items() if "Fuel" not in k
        }
        moon = EveMoon.objects.create(
            system="Jita", planet="IV", moon=4, monthly_net=5
        )
        EveMoonDistribution.objects.create(
            moon=moon, ore="Bitumens", yield_percent=Decimal("0.5")
        )
        update_moon_revenues()
        moon.refresh_from_db()
        self.assertEqual(moon.monthly_revenue, 656_640_000)
        self.assertEqual(moon.monthly_net, 5)


def _killmail(system_id=30002090, alliance=99000001):
    return {
        "killmail_time": "2026-11-10T19:42:00Z",
        "solar_system_id": system_id,
        "victim": {"corporation_id": 98000001, "alliance_id": alliance},
        "attackers": [
            {
                "character_id": 1,
                "corporation_id": 98000002,
                "alliance_id": 99000002,
                "damage_done": 900,
            },
            {
                "character_id": 2,
                "corporation_id": 98000003,
                "damage_done": 100,
            },
        ],
    }


def _response(entries):
    response = MagicMock(status_code=200)
    response.json.return_value = entries
    return response


@patch("moons.metenox.time.sleep")
@patch(
    "moons.metenox.resolve_entity_names",
    return_value={
        98000001: "Holder Corp",
        99000001: "Holder Alliance",
        99000002: "Killer Alliance",
    },
)
class MetenoxSyncTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.delete(CURSOR_KEY)
        self.moon = EveMoon.objects.create(
            system="Gomati", planet="VII", moon=2
        )
        esi = MagicMock()
        esi.get_solar_system.return_value = SimpleNamespace(name="Gomati")
        esi.get_moon.return_value = SimpleNamespace(name="Gomati VII - Moon 2")
        patcher = patch("moons.metenox.EsiClient", return_value=esi)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.esi = esi

    def entries(self, *rows):
        return [
            {"killmail_id": kid, "zkb": {"hash": "h", "locationID": loc}}
            for kid, loc in rows
        ]

    @patch("moons.metenox.fetch_esi_killmail", return_value=_killmail())
    @patch("moons.metenox.zkill_get")
    def test_kill_at_our_moon_is_stored_and_named(self, zkill, *_):
        zkill.side_effect = [
            _response(self.entries((20, 40130002), (19, 40999999))),
            _response([]),
        ]
        self.esi.get_moon.side_effect = [
            SimpleNamespace(name="Gomati VII - Moon 2"),
            SimpleNamespace(name="Gomati II - Moon 9"),
        ]
        result = sync_metenox_kills()
        self.assertEqual(result["stored"], 1)
        kill = MetenoxKill.objects.get()
        self.assertEqual(kill.moon, self.moon)
        self.assertEqual(kill.owner_corporation_name, "Holder Corp")
        self.assertEqual(kill.owner_alliance_name, "Holder Alliance")
        self.assertEqual(kill.killer_name, "Killer Alliance")
        self.assertEqual(kill.attacker_count, 2)
        self.moon.refresh_from_db()
        self.assertEqual(self.moon.eve_moon_id, 40130002)
        self.assertEqual(cache.get(CURSOR_KEY), 20)

    @patch("moons.metenox.fetch_esi_killmail")
    @patch("moons.metenox.zkill_get")
    def test_kill_in_a_system_we_dont_track_needs_no_moon_lookup(
        self, zkill, fetch, *_
    ):
        zkill.side_effect = [
            _response(self.entries((5, 40000001))),
            _response([]),
        ]
        fetch.return_value = _killmail(system_id=30000142)
        self.esi.get_solar_system.return_value = SimpleNamespace(name="Jita")
        sync_metenox_kills()
        self.esi.get_moon.assert_not_called()
        self.assertFalse(MetenoxKill.objects.exists())

    @patch("moons.metenox.fetch_esi_killmail", return_value=_killmail())
    @patch("moons.metenox.zkill_get")
    def test_second_run_stops_at_the_cursor(self, zkill, fetch, *_):
        self.moon.eve_moon_id = 40130002
        self.moon.save()
        zkill.side_effect = [_response(self.entries((10, 40130002)))] + [
            _response([])
        ]
        sync_metenox_kills()
        zkill.side_effect = [
            _response(self.entries((11, 40130002), (10, 40130002)))
        ]
        fetch.reset_mock()
        sync_metenox_kills()
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(MetenoxKill.objects.count(), 2)
        self.assertEqual(cache.get(CURSOR_KEY), 11)

    @patch("moons.metenox.fetch_esi_killmail", return_value=None)
    @patch("moons.metenox.zkill_get")
    def test_failed_killmail_keeps_the_cursor(self, zkill, *_):
        cache.set(CURSOR_KEY, 3)
        zkill.side_effect = [_response(self.entries((4, 40130002), (3, 1)))]
        sync_metenox_kills()
        self.assertEqual(cache.get(CURSOR_KEY), 3)


class MoonNameTests(TestCase):
    def test_parse(self):
        self.assertEqual(
            parse_moon_name("Gomati VII - Moon 2"), ("Gomati", "VII", 2)
        )
        self.assertEqual(
            parse_moon_name("Old Man Star IV - Moon 11"),
            ("Old Man Star", "IV", 11),
        )
        self.assertIsNone(parse_moon_name("Gomati VII"))
