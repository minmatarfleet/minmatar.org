"""Tests for hangar purchase Discord forum threads and ack API."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from buyback.helpers.purchase_discord import (
    format_isk_compact,
    notify_purchase_created,
    notify_purchase_status_changed,
    order_thread_title,
)
from buyback.helpers.purchase_discord_buttons import (
    cancel_custom_id,
    complete_custom_id,
    order_action_components,
    parse_cancel_custom_id,
    parse_complete_custom_id,
)
from buyback.models import (
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    EveBuybackSettings,
    SellPriceBasis,
)
from buyback.tests.helpers import BASE_URL, ensure_type
from discord.models import DiscordChannel, DiscordGuild, DiscordUser
from eveonline.models import EveLocation
from market.models import EveMarketItemLocationPrice


class PurchaseDiscordButtonsTestCase(TestCase):
    def test_custom_id_roundtrip(self):
        self.assertEqual(complete_custom_id(42), "buyback:complete:42")
        self.assertEqual(parse_complete_custom_id("buyback:complete:42"), 42)
        self.assertIsNone(parse_complete_custom_id("buyback:cancel:42"))
        self.assertEqual(cancel_custom_id(7), "buyback:cancel:7")
        self.assertEqual(parse_cancel_custom_id("buyback:cancel:7"), 7)

    def test_order_action_components(self):
        row = order_action_components(99)[0]["components"]
        self.assertEqual(row[0]["label"], "Complete")
        self.assertEqual(row[0]["custom_id"], "buyback:complete:99")
        self.assertEqual(row[0]["style"], 3)
        self.assertEqual(row[1]["label"], "Cancel")
        self.assertEqual(row[1]["custom_id"], "buyback:cancel:99")
        self.assertEqual(row[1]["style"], 4)


class PurchaseDiscordTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=555444333,
            defaults={"name": "Buyback Test Guild", "is_active": True},
        )
        self.channel, _ = DiscordChannel.objects.update_or_create(
            channel_id=1542652883026186320,
            defaults={
                "guild": self.guild,
                "name": "buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_buyback": True,
            },
        )
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.order = BuybackPurchaseOrder.objects.create(
            created_by=self.user,
            character_name="Test Pilot",
            paste="Compressed Veldspar\t10",
            contract_total=3_500_000,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        self.order.lines.create(
            eve_type=self.ore,
            name=self.ore.name,
            quantity=10,
            unit_price=Decimal("350000.00"),
            line_total=Decimal("3500000.00"),
        )

    def test_format_isk_compact(self):
        self.assertEqual(format_isk_compact(3_500_000), "3.5M")
        self.assertEqual(format_isk_compact(850_000), "850K")
        self.assertEqual(format_isk_compact(500), "500")

    def test_thread_title(self):
        self.assertEqual(
            order_thread_title(self.order),
            f"Sale #{self.order.pk} · Test Pilot · 3.5M ISK",
        )

    @patch("buyback.helpers.purchase_discord.discord")
    def test_notify_order_created_stores_thread_id(self, discord_mock):
        response = MagicMock()
        response.json.return_value = {"id": "555666777"}
        discord_mock.create_forum_thread.return_value = response
        channel_response = MagicMock()
        channel_response.json.return_value = {
            "available_tags": [
                {"id": "111", "name": "misc"},
                {"id": "222", "name": "Open"},
            ],
            "flags": 16,
        }
        discord_mock.get_channel.return_value = channel_response

        notify_purchase_created(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.discord_thread_id, 555666777)
        discord_mock.create_forum_thread.assert_called_once()
        kwargs = discord_mock.create_forum_thread.call_args.kwargs
        self.assertEqual(kwargs["channel_id"], self.channel.channel_id)
        self.assertIn(f"Sale #{self.order.pk}", kwargs["title"])
        self.assertEqual(kwargs["applied_tags"], ["222"])
        self.assertEqual(
            kwargs["components"][0]["components"][0]["custom_id"],
            complete_custom_id(self.order.pk),
        )

    @patch("buyback.helpers.purchase_discord.discord")
    def test_notify_skips_without_designated_channel(self, discord_mock):
        DiscordChannel.objects.filter(receive_buyback=True).update(
            receive_buyback=False
        )
        notify_purchase_created(self.order)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.discord_thread_id)
        discord_mock.create_forum_thread.assert_not_called()

    @patch("buyback.helpers.purchase_discord.time.sleep")
    @patch("buyback.helpers.purchase_discord.discord")
    def test_completed_posts_then_closes_thread(
        self, discord_mock, sleep_mock
    ):
        self.order.status = BuybackPurchaseOrder.Status.COMPLETED
        self.order.discord_thread_id = 555
        self.order.save(update_fields=["status", "discord_thread_id"])
        notify_purchase_status_changed(self.order)
        discord_mock.create_message.assert_called_once()
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        self.assertIn("Sale completed", payload["content"])
        sleep_mock.assert_called_once()
        discord_mock.close_thread.assert_called_once_with(channel_id=555)

    @patch("buyback.helpers.purchase_discord.time.sleep")
    @patch("buyback.helpers.purchase_discord.discord")
    def test_cancelled_posts_then_closes_thread(
        self, discord_mock, sleep_mock
    ):
        self.order.status = BuybackPurchaseOrder.Status.CANCELLED
        self.order.discord_thread_id = 777
        self.order.save(update_fields=["status", "discord_thread_id"])
        notify_purchase_status_changed(self.order)
        discord_mock.create_message.assert_called_once()
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        self.assertIn("Sale cancelled", payload["content"])
        sleep_mock.assert_called_once()
        discord_mock.close_thread.assert_called_once_with(channel_id=777)


class PurchaseDiscordAckApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.setup_character()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.manager = User.objects.create(
            username="stock_manager", is_staff=True
        )
        self.staff = User.objects.create(username="bot_service", is_staff=True)
        self.staff_token = jwt.encode(
            {"user_id": self.staff.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        self.bystander = User.objects.create(username="bystander")
        DiscordUser.objects.create(
            id=3001, discord_tag="buyer#0001", user=self.user
        )
        DiscordUser.objects.create(
            id=3002, discord_tag="manager#0001", user=self.manager
        )
        DiscordUser.objects.create(
            id=3003, discord_tag="bystander#0001", user=self.bystander
        )
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        jita = EveLocation.objects.create(
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
        EveMarketItemLocationPrice.objects.create(
            location=jita,
            item=self.water,
            buy_price=Decimal("100.00"),
            sell_price=Decimal("100.00"),
            split_price=Decimal("100.00"),
        )
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            eve_type=self.water,
            quantity=50,
            occurred_at=timezone.now(),
            source_id="in:water",
        )

    def _place(self):
        response = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t10", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_status_changed_task.delay"
    )
    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_complete_by_manager(self, unused_created, unused_status):
        data = self._place()
        self.assertIsNone(data.get("discord_thread_id"))
        order = BuybackPurchaseOrder.objects.get(pk=data["id"])
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            eve_type=self.water,
            quantity=10,
            occurred_at=timezone.now(),
            source_id="out:discord-complete",
            counterparty_id=order.character_id,
        )
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3002, "action": "complete"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "completed")

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_status_changed_task.delay"
    )
    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_complete_by_coordinator(self, unused_created, unused_status):
        coordinator = User.objects.create(username="hangar_coordinator")
        DiscordUser.objects.create(
            id=3004, discord_tag="coord#0001", user=coordinator
        )
        EveBuybackSettings.load().coordinators.add(coordinator)
        data = self._place()
        order = BuybackPurchaseOrder.objects.get(pk=data["id"])
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            eve_type=self.water,
            quantity=10,
            occurred_at=timezone.now(),
            source_id="out:discord-coordinator",
            counterparty_id=order.character_id,
        )
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3004, "action": "complete"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "completed")

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_status_changed_task.delay"
    )
    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_cancel_by_owner(self, unused_created, unused_status):
        data = self._place()
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3001, "action": "cancel"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "cancelled")

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_complete_by_owner_rejected(self, unused_created):
        data = self._place()
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3001, "action": "complete"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 403)

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_wrong_user_rejected(self, unused_created):
        data = self._place()
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3003, "action": "cancel"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 403)

    @patch(
        "buyback.helpers.purchase_orders.notify_buyback_purchase_created_task.delay"
    )
    def test_non_staff_cannot_ack_for_another_user(self, unused_created):
        data = self._place()
        response = self.client.post(
            f"{BASE_URL}/stock/orders/{data['id']}/discord-ack",
            data=json.dumps({"discord_user_id": 3002, "action": "complete"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)
