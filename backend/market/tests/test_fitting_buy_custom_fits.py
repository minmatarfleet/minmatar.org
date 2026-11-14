"""Fitting buy orders made from a pasted EFT fit instead of a site fit."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType
from ninja.testing import TestClient

from fittings.models import EveFitting
from market.endpoints.fitting_buy_orders import router
from market.helpers.fitting_buy_custom import resolve_custom_fit
from market.helpers.fitting_buy_plan import build_shopping_plan
from market.models.fitting_buy_order import FittingBuyOrder
from market.tests.test_fitting_buy_orders import _auth_headers, _type


def _module(type_id: int, name: str) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=7, defaults={"name": "Module", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=60,
        defaults={
            "name": "Damage Control",
            "published": True,
            "eve_category": category,
        },
    )
    obj, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={"name": name, "published": True, "eve_group": group},
    )
    return obj


PASTED_EFT = (
    "[Probe, My Own Probe]\r\n"
    "Damage Control II\r\n"
    "[Empty Low slot]\r\n"
    "1MN Afterburner II /offline\r\n"
    "\r\n"
    "Hobgoblin II x2\r\n"
)


class ResolveCustomFitTestCase(TestCase):
    def setUp(self):
        self.hull = _type(1619, "Probe")
        self.dc = _module(2048, "Damage Control II")
        self.ab = _module(583, "1MN Afterburner II")
        self.drone = _module(2454, "Hobgoblin II")

    def test_resolves_ship_and_fit_name(self):
        fit = resolve_custom_fit(PASTED_EFT)
        self.assertTrue(fit.ok, fit.error)
        self.assertEqual(fit.ship_id, self.hull.id)
        self.assertEqual(fit.ship_name, "Probe")
        self.assertEqual(fit.fit_name, "My Own Probe")
        self.assertNotIn("\r", fit.eft)

    def test_lists_every_unknown_item(self):
        fit = resolve_custom_fit(
            "[Probe, Bad]\nDamage Control II\nWarp Disruptor 9000\n"
            "Not A Drone x3\n"
        )
        self.assertFalse(fit.ok)
        self.assertEqual(
            fit.unknown_names, ["Not A Drone", "Warp Disruptor 9000"]
        )
        self.assertIn("Warp Disruptor 9000", fit.error)
        self.assertIn("Not A Drone", fit.error)

    def test_unknown_hull_is_listed(self):
        fit = resolve_custom_fit("[Probee, Typo]\nDamage Control II\n")
        self.assertFalse(fit.ok)
        self.assertEqual(fit.unknown_names, ["Probee"])

    def test_hull_must_be_a_ship(self):
        fit = resolve_custom_fit("[Damage Control II, Nope]\n")
        self.assertFalse(fit.ok)
        self.assertIn("not a ship", fit.error)

    def test_missing_header(self):
        fit = resolve_custom_fit("Damage Control II\n1MN Afterburner II")
        self.assertFalse(fit.ok)
        self.assertIn("EFT header", fit.error)

    def test_empty(self):
        self.assertFalse(resolve_custom_fit("   ").ok)


@patch("market.endpoints.fitting_buy_orders.post_order.ensure_jita_check")
class CustomFitOrderEndpointTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = TestClient(router)
        self.owner = User.objects.create_user("owner", password="x")
        self.hull = _type(1619, "Probe")
        self.dc = _module(2048, "Damage Control II")
        self.ab = _module(583, "1MN Afterburner II")
        self.drone = _module(2454, "Hobgoblin II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Probe Fit",
            ship_id=self.hull.id,
            description="test",
            eft_format="[Probe, Test Probe]\nDamage Control II\n",
        )

    def _create(self, payload):
        return self.client.post(
            "/fitting-buy-orders",
            json=payload,
            headers=_auth_headers(self.owner),
        )

    def test_pasted_fit_creates_the_same_lines_as_a_site_fit(self, jita_check):
        response = self._create(
            {
                "include_hull": True,
                "custom_fits": [{"eft": PASTED_EFT, "quantity": 3}],
            }
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(len(body["lines"]), 1)
        line = body["lines"][0]
        self.assertIsNone(line["fitting_id"])
        self.assertTrue(line["is_custom"])
        self.assertEqual(line["fitting_name"], "My Own Probe")
        self.assertEqual(line["ship_id"], self.hull.id)
        self.assertEqual(line["quantity"], 3)

        order = FittingBuyOrder.objects.get(pk=body["id"])
        plan = build_shopping_plan(order)
        self.assertEqual(plan.needed[self.hull.id], 3)
        self.assertEqual(plan.needed[self.dc.id], 3)
        self.assertEqual(plan.needed[self.ab.id], 3)
        self.assertEqual(plan.needed[self.drone.id], 6)
        items = {i["type_id"]: i["needed_qty"] for i in body["items"]}
        self.assertEqual(items[self.drone.id], 6)

        # No site fitting is created for a pasted fit.
        self.assertEqual(EveFitting.objects.count(), 1)

    def test_site_fits_and_pasted_fits_on_one_order(self, jita_check):
        response = self._create(
            {
                "lines": [{"fitting_id": self.fitting.id, "quantity": 2}],
                "custom_fits": [{"eft": PASTED_EFT, "quantity": 1}],
            }
        )
        self.assertEqual(response.status_code, 201, response.content)
        lines = response.json()["lines"]
        self.assertEqual(
            [(row["fitting_id"], row["is_custom"]) for row in lines],
            [(self.fitting.id, False), (None, True)],
        )
        items = {
            i["type_id"]: i["needed_qty"] for i in response.json()["items"]
        }
        self.assertEqual(items[self.dc.id], 3)

    def test_unknown_items_are_rejected_with_their_names(self, jita_check):
        response = self._create(
            {
                "custom_fits": [
                    {
                        "eft": "[Probe, Bad]\nDamage Control III\n",
                        "quantity": 1,
                    }
                ]
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Damage Control III", response.json()["detail"])
        self.assertFalse(FittingBuyOrder.objects.exists())

    def test_quantity_must_be_positive(self, jita_check):
        response = self._create(
            {"custom_fits": [{"eft": PASTED_EFT, "quantity": 0}]}
        )
        self.assertEqual(response.status_code, 400)

    def test_needs_a_fit(self, jita_check):
        self.assertEqual(self._create({}).status_code, 400)

    def test_requires_login(self, jita_check):
        response = self.client.post(
            "/fitting-buy-orders",
            json={"custom_fits": [{"eft": PASTED_EFT}]},
        )
        self.assertEqual(response.status_code, 401)

    def test_order_list_and_detail_serialize_pasted_lines(self, jita_check):
        created = self._create(
            {"custom_fits": [{"eft": PASTED_EFT, "quantity": 2}]}
        ).json()
        listing = self.client.get(
            "/fitting-buy-orders", headers=_auth_headers(self.owner)
        )
        self.assertEqual(listing.status_code, 200)
        ship = listing.json()[0]["ships"][0]
        self.assertIsNone(ship["fitting_id"])
        self.assertEqual(ship["fitting_name"], "My Own Probe")
        detail = self.client.get(
            f"/fitting-buy-orders/{created['id']}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Damage Control II", detail.json()["lines"][0]["eft"])


class CustomFitCheckEndpointTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user("pilot", password="x")
        _type(1619, "Probe")
        _module(2048, "Damage Control II")
        _module(583, "1MN Afterburner II")
        _module(2454, "Hobgoblin II")

    def test_ok_fit(self):
        response = self.client.post(
            "/fitting-buy-orders/custom-fit-check",
            json={"eft": PASTED_EFT},
            headers=_auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["ship_id"], 1619)
        self.assertEqual(body["item_count"], 4)

    def test_unknown_items(self):
        response = self.client.post(
            "/fitting-buy-orders/custom-fit-check",
            json={"eft": "[Probe, x]\nMystery Module\n"},
            headers=_auth_headers(self.user),
        )
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["unknown_names"], ["Mystery Module"])
