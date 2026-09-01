"""Tests for fitting buy order planning and permissions."""

from decimal import Decimal
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from eveuniverse.models import (
    EveCategory,
    EveDogmaAttribute,
    EveGroup,
    EveType,
    EveTypeDogmaAttribute,
)
from ninja.testing import TestClient

from fittings.models import EveFitting, EveFittingModuleSubstitution
from market.endpoints.fitting_buy_orders import router
from market.helpers.fitting_buy_check import run_fitting_buy_jita_check
from market.helpers.fitting_buy_eft import effective_eft_for_line
from market.helpers.fitting_buy_jita import (
    JITA_DEPTH_BAND_MIN_PRICE,
    JITA_DEPTH_PRICE_BAND,
    JitaSellDepth,
    compute_banded_sell_depth,
)
from market.helpers.fitting_buy_alternates import (
    DOGMA_CPU_ID,
    DOGMA_POWER_ID,
    price_within_cap,
    shopping_alternate_types_for,
)
from market.helpers.fitting_buy_allocations import (
    AllocationError,
    effective_buy_map,
    set_allocations,
)
from market.helpers.fitting_buy_guide import shopping_landed_complete
from market.helpers.fitting_buy_plan import (
    build_shopping_plan,
    sync_order_items,
)
from market.helpers.fitting_buy_prices import apply_landed_prices
from market.helpers.fitting_buy_serialize import serialize_order_detail
from market.helpers.fitting_buy_swap import apply_swap_on_order
from market.helpers.item_classification import (
    DOGMA_META_GROUP_ID,
    DOGMA_TECH_LEVEL_ID,
    META_GROUP_DEADSPACE,
    META_GROUP_FACTION,
    META_GROUP_OFFICER,
    META_GROUP_STORYLINE,
    META_GROUP_T2,
)
from market.models.fitting_buy_order import (
    FittingBuyJitaCheck,
    FittingBuyJitaCheckStatus,
    FittingBuyOrder,
    FittingBuyOrderLine,
    FittingBuyOrderStatus,
)


def _type(type_id: int, name: str) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=25,
        defaults={
            "name": "Frigate",
            "published": True,
            "eve_category": category,
        },
    )
    obj, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "published": True,
            "eve_group": group,
        },
    )
    return obj


def _ensure_dogma_attr(attr_id: int, name: str) -> None:
    EveDogmaAttribute.objects.get_or_create(
        id=attr_id,
        defaults={
            "name": name,
            "published": True,
            "default_value": 0.0,
            "description": name,
            "display_name": name,
            "high_is_good": False,
            "stackable": True,
        },
    )


def _set_cpu_pg(eve_type: EveType, cpu: float, pg: float) -> None:
    _ensure_dogma_attr(DOGMA_CPU_ID, "cpu")
    _ensure_dogma_attr(DOGMA_POWER_ID, "power")
    EveTypeDogmaAttribute.objects.update_or_create(
        eve_type=eve_type,
        eve_dogma_attribute_id=DOGMA_CPU_ID,
        defaults={"value": cpu},
    )
    EveTypeDogmaAttribute.objects.update_or_create(
        eve_type=eve_type,
        eve_dogma_attribute_id=DOGMA_POWER_ID,
        defaults={"value": pg},
    )


def _auth_headers(user: User) -> dict:
    token = jwt.encode(
        {
            "user_id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class FittingBuyPlanTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("buyer", password="x")
        self.hull = _type(1619, "Probe")
        self.mod_a = _type(2048, "Damage Control II")
        self.mod_b = _type(583, "1MN Afterburner II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Probe Fit",
            ship_id=self.hull.id,
            description="test",
            eft_format=(
                f"[{self.hull.name}, Test Probe]\n"
                f"{self.mod_a.name}\n"
                f"{self.mod_b.name}\n"
            ),
        )
        self.order = FittingBuyOrder.objects.create(owner=self.user)
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=10,
        )

    def test_plan_excludes_hull_by_default(self):
        sync_order_items(self.order)
        plan = build_shopping_plan(self.order)
        self.assertNotIn(self.hull.id, plan.needed)
        self.assertEqual(plan.needed[self.mod_a.id], 10)
        self.assertEqual(plan.buy[self.mod_a.id], 10)

    def test_stock_paste_reduces_buy(self):
        self.order.stock_paste = f"{self.mod_a.name}\t4"
        self.order.save(update_fields=["stock_paste"])
        sync_order_items(self.order)
        plan = build_shopping_plan(self.order)
        self.assertEqual(plan.stock[self.mod_a.id], 4)
        self.assertEqual(plan.buy[self.mod_a.id], 6)

    def test_swap_changes_shopping_list(self):
        sub = _type(2046, "Damage Control I")
        line = self.order.lines.get()
        line.swaps = [
            {
                "preferred_type_id": self.mod_a.id,
                "substitute_type_id": sub.id,
            }
        ]
        line.save(update_fields=["swaps"])
        sync_order_items(self.order)
        plan = build_shopping_plan(self.order)
        self.assertNotIn(self.mod_a.id, plan.needed)
        self.assertEqual(plan.needed[sub.id], 10)

    def test_effective_eft_applies_swaps(self):
        sub = _type(2046, "Damage Control I")
        line = self.order.lines.select_related("fitting").get()
        line.swaps = [
            {
                "preferred_type_id": self.mod_a.id,
                "substitute_type_id": sub.id,
            }
        ]
        line.save(update_fields=["swaps"])
        eft = effective_eft_for_line(line)
        self.assertIn(sub.name, eft)
        self.assertNotIn(self.mod_a.name, eft)
        self.assertIn(self.mod_b.name, eft)

    def test_landed_prices(self):
        sync_order_items(self.order)
        updated, unresolved = apply_landed_prices(
            self.order, f"{self.mod_a.name}\t12345.67"
        )
        self.assertEqual(updated, 1)
        self.assertEqual(unresolved, [])
        item = self.order.items.get(eve_type_id=self.mod_a.id)
        self.assertEqual(item.unit_price, Decimal("12345.67"))


class BandedJitaSellDepthTestCase(TestCase):
    def test_default_band_is_ten_percent(self):
        self.assertEqual(JITA_DEPTH_PRICE_BAND, Decimal("0.10"))

    def test_band_min_price_is_one_million(self):
        self.assertEqual(JITA_DEPTH_BAND_MIN_PRICE, Decimal("1000000"))

    def test_empty_book(self):
        depth = compute_banded_sell_depth([])
        self.assertEqual(depth.volume, 0)
        self.assertEqual(depth.volume_total, 0)
        self.assertIsNone(depth.sell_min)

    def test_excludes_volume_above_band_for_expensive_items(self):
        # Best 1M; 10% band includes <= 1.1M. Deeper 1.2M+ must not count.
        depth = compute_banded_sell_depth(
            [
                (Decimal("1000000"), 10),
                (Decimal("1050000"), 5),
                (Decimal("1100000"), 2),
                (Decimal("1200000"), 50),
                (Decimal("2000000"), 100),
            ]
        )
        self.assertEqual(depth.volume, 17)
        self.assertEqual(depth.volume_total, 167)
        self.assertEqual(depth.order_count, 3)
        self.assertEqual(depth.sell_min, Decimal("1000000"))
        self.assertEqual(depth.sell_band_max, Decimal("1100000"))

    def test_includes_orders_exactly_at_band_edge(self):
        depth = compute_banded_sell_depth(
            [
                (Decimal("1000000"), 1),
                (Decimal("1100000"), 4),
            ]
        )
        self.assertEqual(depth.volume, 5)
        self.assertEqual(depth.sell_band_max, Decimal("1100000"))

    def test_wider_band_includes_more(self):
        depth = compute_banded_sell_depth(
            [
                (Decimal("1000000"), 10),
                (Decimal("1190000"), 3),
                (Decimal("1210000"), 9),
            ],
            price_band=Decimal("0.20"),
        )
        self.assertEqual(depth.volume, 13)
        self.assertEqual(depth.volume_total, 22)

    def test_cheap_items_use_full_book(self):
        # Shade Compact Radar ECM-class: best well under 1M; % jumps are
        # tiny in ISK and must not look like a shortage.
        depth = compute_banded_sell_depth(
            [
                (Decimal("45000"), 10),
                (Decimal("52000"), 40),
                (Decimal("90000"), 100),
            ]
        )
        self.assertEqual(depth.volume, 150)
        self.assertEqual(depth.volume_total, 150)
        self.assertEqual(depth.order_count, 3)
        self.assertEqual(depth.sell_min, Decimal("45000"))
        self.assertEqual(depth.sell_band_max, Decimal("90000"))

    def test_just_below_min_price_uses_full_book(self):
        depth = compute_banded_sell_depth(
            [
                (Decimal("999999"), 2),
                (Decimal("2000000"), 8),
            ]
        )
        self.assertEqual(depth.volume, 10)
        self.assertEqual(depth.volume_total, 10)

    def test_at_min_price_applies_percent_band(self):
        depth = compute_banded_sell_depth(
            [
                (Decimal("1000000"), 2),
                (Decimal("1100000"), 3),
                (Decimal("1100001"), 9),
            ]
        )
        self.assertEqual(depth.volume, 5)
        self.assertEqual(depth.volume_total, 14)
        self.assertEqual(depth.sell_band_max, Decimal("1100000"))

    def test_skips_zero_volume_rows(self):
        depth = compute_banded_sell_depth(
            [
                (Decimal("50"), 0),
                (Decimal("100"), 7),
            ]
        )
        self.assertEqual(depth.volume, 7)
        self.assertEqual(depth.sell_min, Decimal("100"))


class FittingBuyJitaCheckTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("buyer2", password="x")
        self.hull = _type(1620, "Imicus")
        self.mod = _type(2049, "Shield Extender II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Imicus",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, X]\n{self.mod.name}\n",
        )
        self.order = FittingBuyOrder.objects.create(owner=self.user)
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=5,
        )
        sync_order_items(self.order)

    @patch("market.helpers.fitting_buy_check.jita_sell_depth_by_type_id")
    def test_check_applies_usable_depth(self, mock_depth):
        mock_depth.return_value = {
            self.mod.id: JitaSellDepth(
                type_id=self.mod.id,
                volume=3,
                order_count=2,
                sell_min=Decimal("100"),
                fetched_at="2026-01-01T00:00:00+00:00",
                volume_total=80,
                sell_band_max=Decimal("110"),
            )
        }
        check = FittingBuyJitaCheck.objects.create(
            order=self.order,
            started_by=self.user,
            status=FittingBuyJitaCheckStatus.PENDING,
            type_ids=[self.mod.id],
            total_count=1,
        )
        run_fitting_buy_jita_check(check.id)
        check.refresh_from_db()
        self.assertEqual(check.status, FittingBuyJitaCheckStatus.COMPLETE)
        self.assertNotIn("_max_completable", check.results)
        persisted = check.results[str(self.mod.id)]
        self.assertEqual(persisted["volume"], 3)
        self.assertEqual(persisted["volume_total"], 80)
        item = self.order.items.get(eve_type_id=self.mod.id)
        self.assertEqual(item.jita_sell_volume, 3)
        self.assertEqual(item.shortfall, 2)

    @patch("market.helpers.fitting_buy_check.jita_sell_depth_by_type_id")
    def test_check_fetches_short_item_variants(self, mock_depth):
        compact = _type(2051, "Shield Extender Compact")
        compact.eve_group = self.mod.eve_group
        compact.save(update_fields=["eve_group"])
        _set_cpu_pg(self.mod, 20, 1)
        _set_cpu_pg(compact, 20, 1)

        def fake_depth(type_ids, **_kwargs):
            result = {}
            for tid in type_ids:
                volume = 3 if tid == self.mod.id else 40
                result[tid] = JitaSellDepth(
                    type_id=tid,
                    volume=volume,
                    order_count=1,
                    sell_min=Decimal("50"),
                    fetched_at="2026-01-01T00:00:00+00:00",
                )
            return result

        mock_depth.side_effect = fake_depth
        check = FittingBuyJitaCheck.objects.create(
            order=self.order,
            started_by=self.user,
            status=FittingBuyJitaCheckStatus.PENDING,
            type_ids=[self.mod.id],
            total_count=1,
        )
        run_fitting_buy_jita_check(check.id)
        check.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(check.status, FittingBuyJitaCheckStatus.COMPLETE)
        self.assertGreaterEqual(mock_depth.call_count, 2)
        second_ids = set(mock_depth.call_args_list[1].args[0])
        self.assertIn(compact.id, second_ids)
        self.assertEqual(
            self.order.variant_jita_cache[str(compact.id)]["volume"], 40
        )
        detail = serialize_order_detail(self.order, self.user)
        short_item = next(
            item for item in detail["items"] if item["type_id"] == self.mod.id
        )
        compact_alt = next(
            alt
            for alt in short_item["alternates"]
            if alt["type_id"] == compact.id
        )
        self.assertEqual(compact_alt["jita_sell_volume"], 40)


class FittingBuyApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("owner", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.client = TestClient(router)
        self.hull = _type(1621, "Heron")
        self.mod = _type(2050, "Small Shield Extender II")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Heron",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Y]\n{self.mod.name}\n",
        )

    @patch("market.endpoints.fitting_buy_orders.post_order.ensure_jita_check")
    def test_global_list_and_owner_mutate(self, mock_ensure):
        self.assertIsNotNone(mock_ensure)
        order = FittingBuyOrder.objects.create(owner=self.owner)
        response = self.client.get(
            "/fitting-buy-orders", headers=_auth_headers(self.other)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        response = self.client.post(
            f"/fitting-buy-orders/{order.id}/lines",
            json={"fitting_id": self.fitting.id, "quantity": 1},
            headers=_auth_headers(self.other),
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/fitting-buy-orders",
            json={
                "lines": [
                    {"fitting_id": self.fitting.id, "quantity": 2},
                ]
            },
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(len(body["lines"]), 1)
        self.assertEqual(body["lines"][0]["quantity"], 2)
        self.assertIn("eft", body["lines"][0])
        self.assertIn(self.mod.name, body["lines"][0]["eft"])
        self.assertIn("fits_eft", body)
        self.assertTrue(any(i["buy_qty"] == 2 for i in body["items"]))
        self.assertNotIn("title", body)

        patched = self.client.patch(
            f"/fitting-buy-orders/{body['id']}",
            json={"status": FittingBuyOrderStatus.PENDING_FITTING},
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(patched.status_code, 400)

        order = FittingBuyOrder.objects.get(id=body["id"])
        order.jita_checked_at = timezone.now()
        order.save(update_fields=["jita_checked_at"])
        for item in order.items.all():
            item.jita_sell_volume = max(item.buy_qty, 1)
            item.save(update_fields=["jita_sell_volume"])

        patched = self.client.patch(
            f"/fitting-buy-orders/{body['id']}",
            json={"status": FittingBuyOrderStatus.PENDING_FITTING},
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["status"], "pending_fitting")

        listed = self.client.get(
            "/fitting-buy-orders", headers=_auth_headers(self.other)
        ).json()
        self.assertTrue(any(o["id"] == body["id"] for o in listed))
        created = next(o for o in listed if o["id"] == body["id"])
        self.assertEqual(len(created["ships"]), 1)
        self.assertEqual(created["ships"][0]["ship_id"], self.hull.id)

    def test_get_order_is_read_only(self):
        order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrderLine.objects.create(
            order=order,
            fitting=self.fitting,
            quantity=1,
        )
        sync_order_items(order)

        with patch(
            "market.helpers.fitting_buy_check.start_jita_check_async"
        ) as mock_start:
            response = self.client.get(
                f"/fitting-buy-orders/{order.id}",
                headers=_auth_headers(self.owner),
            )
            self.assertEqual(response.status_code, 200)
            mock_start.assert_not_called()

        response = self.client.get(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.other),
        )
        self.assertEqual(response.status_code, 200)

    @patch("market.endpoints.fitting_buy_orders.post_line.ensure_jita_check")
    @patch("market.endpoints.fitting_buy_orders.delete_line.ensure_jita_check")
    def test_owner_can_update_and_remove_lines(
        self, mock_delete_check, mock_post_check
    ):
        order = FittingBuyOrder.objects.create(owner=self.owner)
        line = FittingBuyOrderLine.objects.create(
            order=order,
            fitting=self.fitting,
            quantity=1,
        )
        sync_order_items(order)

        updated = self.client.post(
            f"/fitting-buy-orders/{order.id}/lines",
            json={"fitting_id": self.fitting.id, "quantity": 5},
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["lines"][0]["quantity"], 5)
        mock_post_check.assert_called_once()

        deleted = self.client.delete(
            f"/fitting-buy-orders/{order.id}/lines/{line.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["lines"], [])
        mock_delete_check.assert_called_once()

        forbidden = self.client.delete(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.other),
        )
        self.assertEqual(forbidden.status_code, 403)

        removed = self.client.delete(
            f"/fitting-buy-orders/{order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(FittingBuyOrder.objects.filter(pk=order.id).exists())

    def test_owner_can_delete_order_with_lines_and_items(self):
        order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrderLine.objects.create(
            order=order,
            fitting=self.fitting,
            quantity=2,
        )
        sync_order_items(order)
        self.assertTrue(order.lines.exists())
        self.assertTrue(order.items.exists())

        removed = self.client.delete(
            f"/fitting-buy-orders/{order.id}",
            headers={
                **_auth_headers(self.owner),
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(FittingBuyOrder.objects.filter(pk=order.id).exists())
        self.assertFalse(
            FittingBuyOrderLine.objects.filter(order_id=order.id).exists()
        )

    def test_list_hides_completed_unless_requested(self):
        open_order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrder.objects.create(
            owner=self.owner,
            status=FittingBuyOrderStatus.COMPLETED,
        )
        FittingBuyOrder.objects.create(
            owner=self.other,
            status=FittingBuyOrderStatus.ARCHIVED,
        )

        hidden = self.client.get(
            "/fitting-buy-orders", headers=_auth_headers(self.other)
        )
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual([row["id"] for row in hidden.json()], [open_order.id])

        shown = self.client.get(
            "/fitting-buy-orders?include_completed=true",
            headers=_auth_headers(self.other),
        )
        self.assertEqual(shown.status_code, 200)
        self.assertEqual(len(shown.json()), 3)


class FittingBuyAlternateSwapTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("swapper", password="x")
        self.client = TestClient(router)
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=60,
            defaults={
                "name": "Damage Control",
                "eve_category": category,
                "published": True,
            },
        )
        self.preferred = _type(2046, "Damage Control II")
        self.preferred.eve_group = group
        self.preferred.save(update_fields=["eve_group"])
        self.alternate = _type(5839, "Damage Control I")
        self.alternate.eve_group = group
        self.alternate.save(update_fields=["eve_group"])
        self.compact = _type(
            5841,
            "Damage Control Compact",
        )
        self.compact.eve_group = group
        self.compact.save(update_fields=["eve_group"])
        self.faction = _type(1864, "Republic Fleet Damage Control")
        self.faction.eve_group = group
        self.faction.save(update_fields=["eve_group"])
        self.deadspace = _type(1866, "Corelum C-Type Damage Control")
        self.deadspace.eve_group = group
        self.deadspace.save(update_fields=["eve_group"])
        self.officer = _type(1868, "Chelm's Modified Damage Control")
        self.officer.eve_group = group
        self.officer.save(update_fields=["eve_group"])
        self.named = _type(1870, "Damage Control Dazzler")
        self.named.eve_group = group
        self.named.save(update_fields=["eve_group"])

        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_META_GROUP_ID,
            defaults={
                "name": "metaGroupID",
                "published": True,
                "default_value": 0.0,
                "description": "meta group",
                "display_name": "Meta Group",
                "high_is_good": False,
                "stackable": True,
            },
        )
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_TECH_LEVEL_ID,
            defaults={
                "name": "techLevel",
                "published": True,
                "default_value": 1.0,
                "description": "tech level",
                "display_name": "Tech Level",
                "high_is_good": True,
                "stackable": True,
            },
        )
        for eve_type in (
            self.preferred,
            self.alternate,
            self.compact,
            self.faction,
            self.deadspace,
        ):
            _set_cpu_pg(eve_type, 20, 1)
        for eve_type, meta, tech in (
            (self.preferred, META_GROUP_T2, 2.0),
            (self.alternate, 1.0, 1.0),
            (self.compact, 1.0, 1.0),
            (self.faction, META_GROUP_FACTION, 1.0),
            (self.deadspace, META_GROUP_DEADSPACE, 1.0),
            (self.officer, META_GROUP_OFFICER, 1.0),
            (self.named, META_GROUP_STORYLINE, 1.0),
        ):
            EveTypeDogmaAttribute.objects.update_or_create(
                eve_type=eve_type,
                eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
                defaults={"value": meta},
            )
            EveTypeDogmaAttribute.objects.update_or_create(
                eve_type=eve_type,
                eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
                defaults={"value": tech},
            )

        self.hull = _type(587, "Rifter")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Rifter DC",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Z]\n{self.preferred.name}\n",
        )
        self.order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=10,
        )
        sync_order_items(self.order)
        item = self.order.items.get(eve_type_id=self.preferred.id)
        item.jita_sell_volume = 3
        item.save(update_fields=["jita_sell_volume"])
        self.order.jita_checked_at = timezone.now()
        self.order.save(update_fields=["jita_checked_at"])

    def test_serialize_includes_alternates_for_short_items(self):
        detail = serialize_order_detail(self.order, self.owner)
        short_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.preferred.id
        )
        self.assertTrue(short_item["is_short"])
        alternate_ids = {alt["type_id"] for alt in short_item["alternates"]}
        self.assertIn(self.alternate.id, alternate_ids)
        self.assertIn(self.compact.id, alternate_ids)
        self.assertIn(self.faction.id, alternate_ids)
        self.assertIn(self.deadspace.id, alternate_ids)
        self.assertNotIn(self.officer.id, alternate_ids)
        self.assertNotIn(self.named.id, alternate_ids)

    @patch(
        "market.endpoints.fitting_buy_orders.post_order_swap.ensure_jita_check"
    )
    def test_order_swap_splits_completable_and_short(self, mock_ensure):
        self.assertIsNotNone(mock_ensure)
        # Jita only covers 3 of 10 — apply swap should keep 3 original + 7 swapped.
        updated = apply_swap_on_order(
            self.order,
            preferred_type_id=self.preferred.id,
            substitute_type_id=self.compact.id,
        )
        self.assertEqual(updated, 1)
        line = self.order.lines.get()
        self.assertEqual(line.quantity, 10)
        self.assertEqual(line.swap_hull_qty, 7)
        self.assertEqual(line.swaps[0]["substitute_type_id"], self.compact.id)

        plan = build_shopping_plan(self.order)
        self.assertEqual(plan.buy.get(self.preferred.id), 3)
        self.assertEqual(plan.buy.get(self.compact.id), 7)

        detail = serialize_order_detail(self.order, self.owner)
        self.assertEqual(len(detail["lines"]), 1)
        row = detail["lines"][0]
        self.assertTrue(row["has_swaps"])
        self.assertEqual(row["original_quantity"], 3)
        self.assertEqual(row["swapped_quantity"], 7)
        self.assertIn(self.preferred.name, row["original_eft"])
        self.assertIn(self.compact.name, row["eft"])
        self.assertNotIn(self.preferred.name, row["eft"])
        self.assertIn(self.preferred.name, detail["multibuy"])
        self.assertIn(self.compact.name, detail["multibuy"])

        response = self.client.post(
            f"/fitting-buy-orders/{self.order.id}/swaps",
            json={
                "preferred_type_id": self.preferred.id,
                "substitute_type_id": self.alternate.id,
            },
            headers=_auth_headers(self.owner),
        )
        # Preferred still on the original portion — endpoint should still match.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        buy_items = {
            item["type_id"]: item
            for item in body["items"]
            if item["buy_qty"] > 0
        }
        self.assertIn(self.alternate.id, buy_items)
        self.assertTrue(body["lines"][0]["has_swaps"])


class FittingBuyAllocationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("allocator", password="x")
        self.client = TestClient(router)
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=60,
            defaults={
                "name": "Damage Control",
                "eve_category": category,
                "published": True,
            },
        )
        self.preferred = _type(3046, "Damage Control II")
        self.preferred.eve_group = group
        self.preferred.save(update_fields=["eve_group"])
        self.compact = _type(3048, "Damage Control Compact")
        self.compact.eve_group = group
        self.compact.save(update_fields=["eve_group"])
        self.faction = _type(3050, "Republic Fleet Damage Control")
        self.faction.eve_group = group
        self.faction.save(update_fields=["eve_group"])
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_META_GROUP_ID,
            defaults={
                "name": "metaGroupID",
                "published": True,
                "default_value": 0.0,
                "description": "meta group",
                "display_name": "Meta Group",
                "high_is_good": False,
                "stackable": True,
            },
        )
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_TECH_LEVEL_ID,
            defaults={
                "name": "techLevel",
                "published": True,
                "default_value": 1.0,
                "description": "tech level",
                "display_name": "Tech Level",
                "high_is_good": True,
                "stackable": True,
            },
        )
        _set_cpu_pg(self.preferred, 20, 1)
        _set_cpu_pg(self.compact, 20, 1)
        _set_cpu_pg(self.faction, 20, 1)
        for eve_type, meta, tech in (
            (self.preferred, META_GROUP_T2, 2.0),
            (self.compact, 1.0, 1.0),
            (self.faction, META_GROUP_FACTION, 1.0),
        ):
            EveTypeDogmaAttribute.objects.update_or_create(
                eve_type=eve_type,
                eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
                defaults={"value": meta},
            )
            EveTypeDogmaAttribute.objects.update_or_create(
                eve_type=eve_type,
                eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
                defaults={"value": tech},
            )
        self.hull = _type(588, "Rifter")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Alloc Rifter",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Z]\n{self.preferred.name}\n",
        )
        self.order = FittingBuyOrder.objects.create(owner=self.owner)
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=20,
        )
        sync_order_items(self.order)
        item = self.order.items.get(eve_type_id=self.preferred.id)
        item.jita_sell_volume = 7
        item.save(update_fields=["jita_sell_volume"])
        self.order.jita_checked_at = timezone.now()
        self.order.variant_jita_cache = {
            str(self.compact.id): {
                "volume": 8,
                "order_count": 2,
                "sell_min": "100",
            },
            str(self.faction.id): {
                "volume": 5,
                "order_count": 1,
                "sell_min": "200",
            },
        }
        self.order.save(
            update_fields=[
                "jita_checked_at",
                "variant_jita_cache",
                "updated_at",
            ]
        )

    def test_effective_buy_map_and_multibuy(self):
        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.preferred.id, "qty": 7},
                {"type_id": self.compact.id, "qty": 8},
                {"type_id": self.faction.id, "qty": 5},
            ],
        )
        plan = build_shopping_plan(self.order)
        buy = effective_buy_map(self.order, plan)
        self.assertEqual(buy.get(self.preferred.id), 7)
        self.assertEqual(buy.get(self.compact.id), 8)
        self.assertEqual(buy.get(self.faction.id), 5)
        detail = serialize_order_detail(self.order, self.owner)
        self.assertIn(f"{self.compact.name} 8", detail["multibuy"])
        self.assertIn(f"{self.faction.name} 5", detail["multibuy"])
        self.assertIn(f"{self.preferred.name} 7", detail["multibuy"])
        short_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.preferred.id
        )
        self.assertEqual(short_item["buy_qty"], 7)
        self.assertFalse(short_item["is_short"])
        self.assertTrue(short_item["can_allocate"])
        alloc_ids = {
            row["type_id"]: row["qty"] for row in short_item["allocations"]
        }
        self.assertEqual(alloc_ids[self.compact.id], 8)
        compact_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.compact.id
        )
        self.assertEqual(compact_item["buy_qty"], 8)
        self.assertEqual(
            compact_item["allocated_from_type_id"], self.preferred.id
        )
        faction_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.faction.id
        )
        self.assertEqual(faction_item["buy_qty"], 5)
        self.assertTrue(
            self.order.items.filter(eve_type_id=self.compact.id).exists()
        )
        self.assertTrue(
            self.order.items.filter(eve_type_id=self.faction.id).exists()
        )

    def test_variant_items_keep_landed_prices_across_sync(self):
        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.preferred.id, "qty": 7},
                {"type_id": self.compact.id, "qty": 8},
                {"type_id": self.faction.id, "qty": 5},
            ],
        )
        preferred = self.order.items.get(eve_type_id=self.preferred.id)
        preferred.unit_price = Decimal("100")
        preferred.save(update_fields=["unit_price"])
        self.assertFalse(shopping_landed_complete(self.order))

        updated, unresolved = apply_landed_prices(
            self.order,
            f"{self.compact.name}\t10\n{self.faction.name}\t20",
        )
        self.assertEqual(updated, 2)
        self.assertEqual(unresolved, [])
        self.assertTrue(shopping_landed_complete(self.order))
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.jita_checked_at)

        sync_order_items(self.order)
        compact = self.order.items.get(eve_type_id=self.compact.id)
        self.assertEqual(compact.buy_qty, 8)
        self.assertEqual(compact.needed_qty, 0)
        self.assertEqual(compact.unit_price, Decimal("10"))
        self.assertEqual(compact.jita_sell_volume, 8)
        self.assertTrue(shopping_landed_complete(self.order))
        self.assertIsNotNone(self.order.jita_checked_at)

        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[],
        )
        self.assertFalse(
            self.order.items.filter(eve_type_id=self.compact.id).exists()
        )
        self.assertFalse(
            self.order.items.filter(eve_type_id=self.faction.id).exists()
        )

    def test_get_order_heals_missing_variant_items(self):
        self.order.shopping_allocations = {
            str(self.preferred.id): [
                {"type_id": self.preferred.id, "qty": 7},
                {"type_id": self.compact.id, "qty": 8},
            ]
        }
        self.order.save(update_fields=["shopping_allocations", "updated_at"])
        self.assertFalse(
            self.order.items.filter(eve_type_id=self.compact.id).exists()
        )
        response = self.client.get(
            f"/fitting-buy-orders/{self.order.id}",
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        compact = self.order.items.get(eve_type_id=self.compact.id)
        self.assertEqual(compact.buy_qty, 8)
        self.assertEqual(compact.needed_qty, 0)
        self.assertEqual(compact.jita_sell_volume, 8)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.jita_checked_at)

    def test_rejects_unknown_variant_and_over_sum(self):
        with self.assertRaises(AllocationError):
            set_allocations(
                self.order,
                preferred_type_id=self.preferred.id,
                entries=[
                    {"type_id": self.preferred.id, "qty": 20},
                    {"type_id": 999999, "qty": 1},
                ],
            )
        item = self.order.items.get(eve_type_id=self.preferred.id)
        item.jita_sell_volume = None
        item.save(update_fields=["jita_sell_volume"])
        with self.assertRaises(AllocationError):
            set_allocations(
                self.order,
                preferred_type_id=self.preferred.id,
                entries=[
                    {"type_id": self.preferred.id, "qty": 20},
                    {"type_id": self.compact.id, "qty": 8},
                ],
            )

    def test_allows_partial_split(self):
        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.compact.id, "qty": 8},
            ],
        )
        plan = build_shopping_plan(self.order)
        buy = effective_buy_map(self.order, plan)
        self.assertEqual(buy.get(self.compact.id), 8)
        self.assertEqual(buy.get(self.preferred.id), 12)
        self.assertNotIn(self.faction.id, buy)
        detail = serialize_order_detail(self.order, self.owner)
        self.assertIn(f"{self.compact.name} 8", detail["multibuy"])
        self.assertIn(f"{self.preferred.name} 12", detail["multibuy"])
        line = detail["lines"][0]
        copies = line["fit_copies"]
        self.assertEqual(len(copies), 2)
        by_swapped = {copy["is_swapped"]: copy for copy in copies}
        self.assertEqual(by_swapped[False]["quantity"], 12)
        self.assertEqual(by_swapped[True]["quantity"], 8)
        self.assertIn(self.compact.name, by_swapped[True]["eft"])
        self.assertNotIn(self.compact.name, by_swapped[False]["eft"])
        self.assertEqual(by_swapped[True]["variant_name"], self.compact.name)

    def test_clamps_to_jita_depth(self):
        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.preferred.id, "qty": 7},
                {"type_id": self.compact.id, "qty": 40},
                {"type_id": self.faction.id, "qty": 5},
            ],
        )
        compact_qty = next(
            entry["qty"]
            for entry in self.order.shopping_allocations[
                str(self.preferred.id)
            ]
            if entry["type_id"] == self.compact.id
        )
        self.assertEqual(compact_qty, 8)

        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.preferred.id, "qty": 7},
                {"type_id": self.compact.id, "qty": 40},
            ],
        )
        plan = build_shopping_plan(self.order)
        buy = effective_buy_map(self.order, plan)
        self.assertEqual(buy.get(self.compact.id), 8)
        self.assertEqual(buy.get(self.preferred.id), 12)

    @patch("market.helpers.fitting_buy_check.start_jita_check_async")
    def test_put_allocations_does_not_refetch_jita(self, mock_start):
        response = self.client.put(
            f"/fitting-buy-orders/{self.order.id}/allocations",
            json={
                "preferred_type_id": self.preferred.id,
                "entries": [
                    {"type_id": self.preferred.id, "qty": 7},
                    {"type_id": self.compact.id, "qty": 8},
                    {"type_id": self.faction.id, "qty": 5},
                ],
            },
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        mock_start.assert_not_called()
        body = response.json()
        self.assertIn(f"{self.compact.name} 8", body["multibuy"])
        self.assertNotIn("Damage Control Compact 20", body["multibuy"])

    @patch("market.helpers.fitting_buy_check.start_jita_check_async")
    def test_put_partial_split_returns_200(self, mock_start):
        response = self.client.put(
            f"/fitting-buy-orders/{self.order.id}/allocations",
            json={
                "preferred_type_id": self.preferred.id,
                "entries": [
                    {"type_id": self.faction.id, "qty": 5},
                ],
            },
            headers=_auth_headers(self.owner),
        )
        self.assertEqual(response.status_code, 200)
        mock_start.assert_not_called()
        body = response.json()
        self.assertIn(f"{self.faction.name} 5", body["multibuy"])
        self.assertIn(f"{self.preferred.name} 15", body["multibuy"])


class FittingBuyAlternateFitFilterTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("fitfilter", password="x")
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=60,
            defaults={
                "name": "Damage Control",
                "eve_category": category,
                "published": True,
            },
        )
        self.preferred = _type(4046, "Damage Control II")
        self.preferred.eve_group = group
        self.preferred.save(update_fields=["eve_group"])
        self.faction = _type(4048, "Republic Fleet Damage Control")
        self.faction.eve_group = group
        self.faction.save(update_fields=["eve_group"])
        self.compact = _type(4050, "Damage Control Compact")
        self.compact.eve_group = group
        self.compact.save(update_fields=["eve_group"])
        self.navy = _type(4052, "Federation Navy Damage Control")
        self.navy.eve_group = group
        self.navy.save(update_fields=["eve_group"])
        self.heavy = _type(4054, "Shadow Serpentis Damage Control")
        self.heavy.eve_group = group
        self.heavy.save(update_fields=["eve_group"])
        self.officer = _type(4056, "Chelm's Modified Damage Control")
        self.officer.eve_group = group
        self.officer.save(update_fields=["eve_group"])
        self.named = _type(4058, "Damage Control Dazzler")
        self.named.eve_group = group
        self.named.save(update_fields=["eve_group"])
        self.missing = _type(4060, "Imperial Navy Damage Control")
        self.missing.eve_group = group
        self.missing.save(update_fields=["eve_group"])
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_META_GROUP_ID,
            defaults={
                "name": "metaGroupID",
                "published": True,
                "default_value": 0.0,
                "description": "meta group",
                "display_name": "Meta Group",
                "high_is_good": False,
                "stackable": True,
            },
        )
        for eve_type, meta in (
            (self.preferred, META_GROUP_T2),
            (self.faction, META_GROUP_FACTION),
            (self.navy, META_GROUP_FACTION),
            (self.heavy, META_GROUP_FACTION),
            (self.officer, META_GROUP_OFFICER),
            (self.named, META_GROUP_STORYLINE),
            (self.missing, META_GROUP_FACTION),
            (self.compact, 1.0),
        ):
            EveTypeDogmaAttribute.objects.update_or_create(
                eve_type=eve_type,
                eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
                defaults={"value": meta},
            )
        _set_cpu_pg(self.preferred, 33, 1)
        _set_cpu_pg(self.faction, 33, 1)
        _set_cpu_pg(self.navy, 16, 1)
        _set_cpu_pg(self.compact, 12, 1)
        _set_cpu_pg(self.heavy, 40, 1)
        _set_cpu_pg(self.officer, 16, 1)
        _set_cpu_pg(self.named, 16, 1)
        self.hull = _type(589, "Rifter")
        self.fitting = EveFitting.objects.create(
            name="[TEST] Fit filter",
            ship_id=self.hull.id,
            description="test",
            eft_format=f"[{self.hull.name}, Z]\n{self.preferred.name}\n",
        )
        self.order = FittingBuyOrder.objects.create(owner=self.user)
        FittingBuyOrderLine.objects.create(
            order=self.order,
            fitting=self.fitting,
            quantity=5,
        )
        sync_order_items(self.order)
        item = self.order.items.get(eve_type_id=self.preferred.id)
        item.jita_sell_volume = 1
        item.jita_sell_min = Decimal("1200000")
        item.save(update_fields=["jita_sell_volume", "jita_sell_min"])
        self.order.jita_checked_at = timezone.now()
        self.order.variant_jita_cache = {
            str(self.faction.id): {
                "volume": 10,
                "order_count": 1,
                "sell_min": "1500000",
            },
            str(self.compact.id): {
                "volume": 40,
                "order_count": 2,
                "sell_min": "200000",
            },
            str(self.navy.id): {
                "volume": 20,
                "order_count": 3,
                "sell_min": "900000",
            },
        }
        self.order.save(
            update_fields=[
                "jita_checked_at",
                "variant_jita_cache",
                "updated_at",
            ]
        )

    def test_lower_or_equal_cpu_pg_kept_higher_excluded(self):
        names = {
            row.name for row in shopping_alternate_types_for(self.preferred)
        }
        self.assertIn(self.faction.name, names)
        self.assertIn(self.navy.name, names)
        self.assertIn(self.compact.name, names)
        self.assertNotIn(self.heavy.name, names)
        self.assertNotIn(self.officer.name, names)
        self.assertNotIn(self.named.name, names)
        self.assertNotIn(self.missing.name, names)
        detail = serialize_order_detail(self.order, self.user)
        short_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.preferred.id
        )
        self.assertEqual(short_item["cpu"], 33.0)
        self.assertEqual(short_item["pg"], 1.0)
        alt_by_id = {alt["type_id"]: alt for alt in short_item["alternates"]}
        self.assertIn(self.faction.id, alt_by_id)
        self.assertIn(self.navy.id, alt_by_id)
        self.assertIn(self.compact.id, alt_by_id)
        self.assertNotIn(self.heavy.id, alt_by_id)
        self.assertEqual(alt_by_id[self.navy.id]["cpu"], 16.0)
        self.assertEqual(alt_by_id[self.navy.id]["pg"], 1.0)
        self.assertEqual(
            alt_by_id[self.faction.id]["jita_sell_min"], "1500000"
        )

    def test_listed_substitution_allows_higher_cpu(self):
        EveFittingModuleSubstitution.objects.create(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.heavy,
        )
        names = {
            row.name
            for row in shopping_alternate_types_for(
                self.preferred,
                listed_substitute_ids={self.heavy.id},
            )
        }
        self.assertIn(self.heavy.name, names)
        detail = serialize_order_detail(self.order, self.user)
        short_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.preferred.id
        )
        alt_ids = {alt["type_id"] for alt in short_item["alternates"]}
        self.assertIn(self.heavy.id, alt_ids)

    def test_listed_substitution_allows_missing_dogma(self):
        EveFittingModuleSubstitution.objects.create(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.missing,
        )
        names = {
            row.name
            for row in shopping_alternate_types_for(
                self.preferred,
                listed_substitute_ids={self.missing.id},
            )
        }
        self.assertIn(self.missing.name, names)

    def test_allocation_allows_lower_cpu_navy(self):
        set_allocations(
            self.order,
            preferred_type_id=self.preferred.id,
            entries=[
                {"type_id": self.preferred.id, "qty": 1},
                {"type_id": self.navy.id, "qty": 4},
            ],
        )
        plan = build_shopping_plan(self.order)
        buy = effective_buy_map(self.order, plan)
        self.assertEqual(buy.get(self.navy.id), 4)
        self.assertEqual(buy.get(self.preferred.id), 1)

    def test_explosive_does_not_match_kinetic(self):
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        hardeners, _ = EveGroup.objects.get_or_create(
            id=328,
            defaults={
                "name": "Armor Hardener",
                "eve_category": category,
                "published": True,
            },
        )
        explosive = _type(60001, "Domination Explosive Armor Hardener")
        explosive.eve_group = hardeners
        explosive.save(update_fields=["eve_group"])
        navy = _type(60002, "Federation Navy Explosive Armor Hardener")
        navy.eve_group = hardeners
        navy.save(update_fields=["eve_group"])
        kinetic = _type(60003, "Federation Navy Kinetic Armor Hardener")
        kinetic.eve_group = hardeners
        kinetic.save(update_fields=["eve_group"])
        EveTypeDogmaAttribute.objects.update_or_create(
            eve_type=explosive,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            defaults={"value": META_GROUP_FACTION},
        )
        EveTypeDogmaAttribute.objects.update_or_create(
            eve_type=navy,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            defaults={"value": META_GROUP_FACTION},
        )
        EveTypeDogmaAttribute.objects.update_or_create(
            eve_type=kinetic,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            defaults={"value": META_GROUP_FACTION},
        )
        _set_cpu_pg(explosive, 33, 1)
        _set_cpu_pg(navy, 16, 1)
        _set_cpu_pg(kinetic, 16, 1)
        names = {row.name for row in shopping_alternate_types_for(explosive)}
        self.assertIn(navy.name, names)
        self.assertNotIn(kinetic.name, names)

    def test_price_cap_keeps_under_excludes_at_or_over(self):
        self.assertTrue(price_within_cap(Decimal("100"), Decimal("149")))
        self.assertFalse(price_within_cap(Decimal("100"), Decimal("150")))
        self.assertFalse(price_within_cap(Decimal("100"), Decimal("200")))
        self.assertTrue(price_within_cap(Decimal("100"), None))
        self.assertTrue(price_within_cap(None, Decimal("200")))
        prices = {
            self.preferred.id: Decimal("100"),
            self.navy.id: Decimal("149"),
            self.compact.id: Decimal("150"),
            self.faction.id: Decimal("200"),
        }
        names = {
            row.name
            for row in shopping_alternate_types_for(
                self.preferred,
                jita_sell_min_by_type=prices,
            )
        }
        self.assertIn(self.navy.name, names)
        self.assertNotIn(self.compact.name, names)
        self.assertNotIn(self.faction.name, names)

    def test_price_cap_keeps_missing_price(self):
        names = {
            row.name
            for row in shopping_alternate_types_for(
                self.preferred,
                jita_sell_min_by_type={self.preferred.id: Decimal("100")},
            )
        }
        self.assertIn(self.navy.name, names)
        self.assertIn(self.compact.name, names)
        self.assertIn(self.faction.name, names)

    def test_price_cap_excludes_listed_substitute(self):
        EveFittingModuleSubstitution.objects.create(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.heavy,
        )
        names = {
            row.name
            for row in shopping_alternate_types_for(
                self.preferred,
                listed_substitute_ids={self.heavy.id},
                jita_sell_min_by_type={
                    self.preferred.id: Decimal("100"),
                    self.heavy.id: Decimal("200"),
                },
            )
        }
        self.assertNotIn(self.heavy.name, names)

    def test_serialize_and_allocation_exclude_expensive(self):
        cache_row = dict(self.order.variant_jita_cache)
        cache_row[str(self.faction.id)] = {
            "volume": 10,
            "order_count": 1,
            "sell_min": "2000000",
        }
        self.order.variant_jita_cache = cache_row
        self.order.save(update_fields=["variant_jita_cache", "updated_at"])
        detail = serialize_order_detail(self.order, self.user)
        short_item = next(
            item
            for item in detail["items"]
            if item["type_id"] == self.preferred.id
        )
        alt_ids = {alt["type_id"] for alt in short_item["alternates"]}
        self.assertNotIn(self.faction.id, alt_ids)
        self.assertIn(self.navy.id, alt_ids)
        with self.assertRaises(AllocationError):
            set_allocations(
                self.order,
                preferred_type_id=self.preferred.id,
                entries=[
                    {"type_id": self.faction.id, "qty": 1},
                ],
            )
