# flake8: noqa
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client

from app.test import TestCase
from moons.helpers import calc_metanox_yield
from moons.models import EveMoon, EveMoonDistribution
from moons.router import count_scanned_moons
from moons.tasks import update_moon_revenues

from .parser import process_moon_paste

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

    def test_process_moon_paste(self):
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

    def test_moon_revenue(self):
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
