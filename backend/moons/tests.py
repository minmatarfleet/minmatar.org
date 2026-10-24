# flake8: noqa
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveMarketPrice, EveType

from app.test import TestCase
from eveonline.models import EveLocation
from industry.helpers.compressed_ore import FALLBACK_MOON_YIELDS_PER_100
from market.models.history import EveMarketItemHistory
from moons.helpers import calc_metanox_yield
from moons.models import EveMoon, EveMoonDistribution
from moons.parser import process_moon_paste
from moons.router import count_scanned_moons
from moons.models import ore_yield_map
from moons.tasks import get_prices, update_moon_revenues

BASE_URL = "/api/moons"

paste = """
Moon	Moon Product	Quantity	Ore TypeID	SolarSystemID	PlanetID	MoonID
Rahadalon V - Moon 2						
	Bitumens	0.5413627028	45492	30002982	40189228	40189231
	Sylvite	0.2586372793	45491	30002982	40189228	40189231
Rahadalon VI - Moon 1						
	Bitumens	0.2821700573	45492	30002982	40189232	40189233
	Cobaltite	0.08585818857	45494	30002982	40189232	40189233
	Sylvite	0.2980297208	45491	30002982	40189232	40189233
	Vanadinite	0.3339420557	45500	30002982	40189232	40189233
Rahadalon VI - Moon 4						
	Chromite	0.2833463252	45501	30002982	40189232	40189236
	Sylvite	0.175055027	45491	30002982	40189232	40189236
	Zeolites	0.34159863	45490	30002982	40189232	40189236
Rahadalon VII - Moon 7						
	Bitumens	0.5342812538	45492	30002982	40189237	40189244
	Coesite	0.2657187581	45493	30002982	40189237	40189244
Rahadalon VIII - Moon 1						
	Bitumens	0.5284282565	45492	30002982	40189245	40189246
	Sylvite	0.2715717256	45491	30002982	40189245	40189246
"""


# Create your tests here.
class EveMoonPasteTestCase(TestCase):
    """Test case for the moon paste parser."""

    @patch("moons.parser.EsiClient")
    def test_process_moon_paste(self, mock_esi_cls):
        mock_esi = mock_esi_cls.return_value
        systems = {30002982: "Rahadalon"}
        planets = {
            40189228: "Rahadalon V",
            40189232: "Rahadalon VI",
            40189237: "Rahadalon VII",
            40189245: "Rahadalon VIII",
        }
        moons = {
            40189231: "Rahadalon V - Moon 2",
            40189233: "Rahadalon VI - Moon 1",
            40189236: "Rahadalon VI - Moon 4",
            40189244: "Rahadalon VII - Moon 7",
            40189246: "Rahadalon VIII - Moon 1",
        }

        def get_solar_system(system_id):
            system = MagicMock()
            system.name = systems[system_id]
            return system

        def get_planet(planet_id):
            planet = MagicMock()
            planet.name = planets[planet_id]
            return planet

        def get_moon(moon_id):
            moon = MagicMock()
            moon.name = moons[moon_id]
            return moon

        mock_esi.get_solar_system.side_effect = get_solar_system
        mock_esi.get_planet.side_effect = get_planet
        mock_esi.get_moon.side_effect = get_moon

        user = User.objects.create_user(
            "tester", "tester@testing.org", "notsosecret"
        )

        process_moon_paste(paste, user.id)

        self.assertEqual(EveMoon.objects.count(), 5)
        self.assertEqual(EveMoonDistribution.objects.count(), 13)
        self.assertEqual(
            EveMoonDistribution.objects.filter(ore="Bitumens").count(), 4
        )
        self.assertEqual(
            "tester", EveMoon.objects.first().reported_by.username
        )


class EveMoonYieldTestCase(TestCase):
    """Test case for moon yield calculations."""

    def test_moon_yield(self):
        distributions = [
            # Use "Rahadalon V - Moon 2" as an example
            EveMoonDistribution(
                moon=None, ore="Bitumens", yield_percent=Decimal(0.5413627028)
            ),
            EveMoonDistribution(
                moon=None, ore="Sylvite", yield_percent=Decimal(0.2586372793)
            ),
        ]

        yields = calc_metanox_yield(distributions)

        self.assertEqual(422, int(yields["Hydrocarbons"]))
        self.assertEqual(201, int(yields["Evaporite Deposits"]))

    def test_products_shared_by_several_ores_add_up(self):
        bitumens = EveMoonDistribution(
            moon=None, ore="Bitumens", yield_percent=Decimal("0.5413627028")
        )
        sylvite = EveMoonDistribution(
            moon=None, ore="Sylvite", yield_percent=Decimal("0.2586372793")
        )

        both = calc_metanox_yield([bitumens, sylvite])
        alone_b = calc_metanox_yield([bitumens])
        alone_s = calc_metanox_yield([sylvite])

        for product in ("Pyerite", "Mexallon"):
            self.assertEqual(
                both[product], alone_b[product] + alone_s[product]
            )
        # Products only one ore makes are unchanged.
        self.assertEqual(both["Hydrocarbons"], alone_b["Hydrocarbons"])
        self.assertEqual(
            both["Evaporite Deposits"], alone_s["Evaporite Deposits"]
        )

    @patch("moons.tasks.get_prices")
    def test_moon_revenue(self, mock_get_prices):
        mock_get_prices.return_value = {
            "Hydrocarbons": Decimal("100"),
            "Pyerite": Decimal("100"),
            "Mexallon": Decimal("100"),
        }
        moon = EveMoon.objects.create(
            system="Jita",
            planet="IV",
            moon=4,
        )
        EveMoonDistribution.objects.create(
            moon=moon,
            ore="Bitumens",
            yield_percent=0.5413627028,
        )

        update_moon_revenues()

        updated_moon = EveMoon.objects.get(id=moon.id)

        self.assertGreater(updated_moon.monthly_revenue, 500000000)


class MoonProductPricesTestCase(TestCase):
    """Moon products priced from stored Forge history, newest day first."""

    def setUp(self):
        super().setUp()
        category, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": category,
            },
        )
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        self.types = {}
        for type_id, name in (
            (35, "Pyerite"),
            (36, "Mexallon"),
            (16633, "Hydrocarbons"),
        ):
            self.types[name] = EveType.objects.create(
                id=type_id, name=name, published=True, eve_group=group
            )
        self.today = timezone.now().date()

    def _history(self, name, days_ago, average):
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.types[name],
            date=self.today - timedelta(days=days_ago),
            average=Decimal(average),
            highest=Decimal(average),
            lowest=Decimal(average),
            volume=1,
        )

    @patch("market.tasks.fetch_market_item_history_for_type.apply_async")
    def test_uses_latest_day_not_oldest(self, unused_apply_async):
        # ESI returns history oldest-first; the old task priced on [0].
        self._history("Pyerite", 400, "31.52")
        self._history("Pyerite", 1, "17.04")
        self.assertEqual(get_prices()["Pyerite"], Decimal("17.04"))

    @patch("market.tasks.fetch_market_item_history_for_type.apply_async")
    def test_empty_history_falls_back_then_omits(self, apply_async):
        EveMarketPrice.objects.create(
            eve_type=self.types["Mexallon"], average_price=55.5
        )
        prices = get_prices()  # must not raise on empty history
        self.assertEqual(prices["Mexallon"], Decimal("55.5"))
        self.assertNotIn("Hydrocarbons", prices)
        queued = {call.kwargs["args"][0] for call in apply_async.mock_calls}
        self.assertEqual(
            queued,
            {t.id for t in self.types.values()},
        )

    @patch("market.tasks.fetch_market_item_history_for_type.apply_async")
    def test_only_stale_history_is_refetched(self, apply_async):
        for name in self.types:
            self._history(name, 5 if name == "Pyerite" else 0, "10")
        get_prices()
        queued = [call.kwargs["args"][0] for call in apply_async.mock_calls]
        self.assertEqual(queued, [self.types["Pyerite"].id])

    @patch("moons.tasks.get_prices")
    def test_missing_product_price_keeps_last_revenue(self, mock_get_prices):
        mock_get_prices.return_value = {
            "Pyerite": Decimal("100"),
            "Mexallon": Decimal("100"),
        }
        moon = EveMoon.objects.create(
            system="Jita", planet="IV", moon=4, monthly_revenue=123
        )
        EveMoonDistribution.objects.create(
            moon=moon, ore="Bitumens", yield_percent=0.5
        )
        update_moon_revenues()
        moon.refresh_from_db()
        self.assertEqual(moon.monthly_revenue, 123)

    @patch("moons.tasks.get_prices")
    def test_revenue_snapshot(self, mock_get_prices):
        mock_get_prices.return_value = {
            "Hydrocarbons": Decimal("400"),
            "Pyerite": Decimal("17"),
            "Mexallon": Decimal("60"),
        }
        moon = EveMoon.objects.create(system="Jita", planet="IV", moon=4)
        EveMoonDistribution.objects.create(
            moon=moon, ore="Bitumens", yield_percent=Decimal("0.5")
        )
        update_moon_revenues()
        moon.refresh_from_db()
        # 0.5 × 12 portions/h × (65×400 + 6000×17 + 400×60) × 24 × 30
        self.assertEqual(moon.monthly_revenue, 656_640_000)

    def test_yield_table_matches_compressed_ore_fallback(self):
        """The two hand-typed moon yield tables must not drift apart."""
        for ore, yields in FALLBACK_MOON_YIELDS_PER_100.items():
            self.assertEqual(
                {k: float(v) for k, v in ore_yield_map[ore].items() if v},
                yields,
                ore,
            )


class EveMoonQueryTest(TestCase):
    """Test case for moon queries"""

    def test_moon_count(self):
        moons = [
            EveMoon(system="Jita", planet="IV", moon=4),
            EveMoon(system="Jita", planet="VI", moon=2),
        ]

        summary = count_scanned_moons(moons)

        self.assertEqual("Jita", summary[0].system)
        self.assertEqual(2, summary[0].scanned_moons)


class EveMoonRouterTest(TestCase):
    """Tests for the EveMoon router"""

    def setUp(self):
        self.client = Client()

        return super().setUp()

    def test_get_moons(self):
        EveMoon.objects.create(
            system="Hek",
            planet="1",
            moon="1",
        )

        response = self.client.get(
            f"{BASE_URL}?system=Hek",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(403, response.status_code)

        self.make_superuser()

        response = self.client.get(
            f"{BASE_URL}?system=Hek",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        moons = response.json()
        self.assertEqual(1, len(moons))


class MoonReportSurvivesReporterDeleteTest(TestCase):
    """The scan belongs to the alliance, not the pilot who reported it."""

    def test_deleting_reporter_keeps_the_moon(self):
        reporter = User.objects.create(username="scanner")
        moon = EveMoon.objects.create(
            system="Hek",
            planet="1",
            moon=2,
            reported_by=reporter,
        )
        EveMoonDistribution.objects.create(
            moon=moon,
            ore="Bitumens",
            yield_percent=Decimal("0.5"),
        )

        reporter.delete()

        moon.refresh_from_db()
        self.assertIsNone(moon.reported_by_id)
        self.assertEqual(
            EveMoonDistribution.objects.filter(moon=moon).count(), 1
        )
