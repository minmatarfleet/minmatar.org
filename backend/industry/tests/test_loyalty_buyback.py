"""Tests for LP buyback market orders API and Discord mirror."""

import json
from unittest.mock import MagicMock, patch

import jwt
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client

from app.test import TestCase as AppTestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import (
    AffiliationType,
    PilotFeature,
    UserAffiliation,
)
from discord.models import DiscordChannel, DiscordGuild, DiscordUser
from industry.helpers.lp_buyback_discord import (
    _awaiting_isk_message,
    _awaiting_lp_message,
    notify_order_created,
    notify_order_status_changed,
    order_thread_title,
)
from industry.helpers.lp_buyback_discord_buttons import (
    isk_sent_custom_id,
    lp_sent_components,
    lp_sent_custom_id,
    parse_isk_sent_custom_id,
    parse_lp_sent_custom_id,
)
from industry.helpers.lp_market_orders import MAX_SELL_LP, format_lp_quantity
from industry.helpers.lp_ledger import account_balance, post_ledger_entry
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointLedgerEntry,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

TLIB_CORP_ID = 1000182


class LpMarketOrderHelpersTestCase(AppTestCase):
    def test_format_lp_quantity(self):
        self.assertEqual(format_lp_quantity(2_500_000), "2.5M")
        self.assertEqual(format_lp_quantity(850_000), "850K")
        self.assertEqual(format_lp_quantity(500), "500")


class LoyaltyBuybackApiTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        clear_feature_cache()
        self.client = Client()
        self.character = EveCharacter.objects.create(
            character_id=999501,
            character_name="LP Seller",
            user=self.user,
        )
        set_primary_character(self.user, self.character)

        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        for corp_id, name in (
            (1000179, "24th Imperial Crusade"),
            (1000180, "State Protectorate"),
            (1000181, "Federal Defense Union"),
        ):
            IndustryLoyaltyPoint.objects.update_or_create(
                corporation_id=corp_id,
                defaults={
                    "name": name,
                    "default_isk_per_lp": 800,
                    "is_active": True,
                },
            )

        self.stockpile = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="FL33T TLIB pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
        )
        post_ledger_entry(self.stockpile, 100_000, 800)

        affiliation_group = Group.objects.create(name="Alliance LP Test")
        affiliation = AffiliationType.objects.create(
            name="Alliance",
            group=affiliation_group,
            priority=910,
            default=False,
        )
        UserAffiliation.objects.create(user=self.user, affiliation=affiliation)

        self.manager = User.objects.create(username="conversion")
        manager_char = EveCharacter.objects.create(
            character_id=999502,
            character_name="LP Buyer",
            user=self.manager,
        )
        set_primary_character(self.manager, manager_char)
        manager_payload = {"user_id": self.manager.id}
        self.manager_token = jwt.encode(
            manager_payload, settings.SECRET_KEY, algorithm="HS256"
        )

        tribe = Tribe.objects.create(
            name="Supply", slug="supply", chief=self.manager
        )
        self.lp_tribe_group = TribeGroup.objects.create(
            tribe=tribe,
            name="Loyalty Points",
            code="supply.loyalty-points",
        )
        TribeGroupMembership.objects.create(
            user=self.manager,
            tribe_group=self.lp_tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        SyncPilotFeaturesCommand().handle()
        trade = PilotFeature.objects.get(code="industry.loyalty.trade")
        trade.affiliations.set([affiliation])
        manage = PilotFeature.objects.get(code="industry.loyalty.manage")
        manage.tribe_groups.set([self.lp_tribe_group])
        clear_feature_cache()

    def test_get_currencies_public(self):
        response = self.client.get("/api/industry/loyalty/currencies")
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.json()}
        self.assertIn("Tribal Liberation Force", names)
        self.assertEqual(len(response.json()), 4)

    def test_get_stockpiles_public(self):
        response = self.client.get("/api/industry/loyalty/stockpiles")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["account_name"], "FL33T TLIB pot")
        self.assertEqual(data[0]["balance"], 100_000)

    def test_get_ledger_returns_chronological_entries(self):
        seller = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="External seller",
            role=IndustryLoyaltyPointAccount.Role.SELLER,
        )
        older = post_ledger_entry(seller, 50_000, 825, notes="admin intake")
        newer = post_ledger_entry(self.stockpile, -10_000, 800, notes="draw")

        response = self.client.get("/api/industry/loyalty/ledger")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 3)
        ids = [row["id"] for row in data]
        self.assertLess(ids.index(newer.pk), ids.index(older.pk))

        stockpile_row = next(row for row in data if row["id"] == newer.pk)
        self.assertEqual(stockpile_row["account_name"], "FL33T TLIB pot")
        self.assertEqual(stockpile_row["amount"], -10_000)
        self.assertEqual(stockpile_row["isk_per_lp"], 800)
        self.assertEqual(stockpile_row["balance_after"], 90_000)
        self.assertEqual(stockpile_row["notes"], "draw")
        self.assertEqual(
            stockpile_row["loyalty_point_name"], "Tribal Liberation Force"
        )

        filtered = self.client.get(
            f"/api/industry/loyalty/ledger?account_id={seller.pk}"
        )
        self.assertEqual(filtered.status_code, 200)
        filtered_ids = {row["id"] for row in filtered.json()}
        self.assertIn(older.pk, filtered_ids)
        self.assertNotIn(newer.pk, filtered_ids)

    def test_get_ledger_respects_limit(self):
        for i in range(3):
            post_ledger_entry(self.stockpile, 1_000, 800, notes=f"lot {i}")
        response = self.client.get("/api/industry/loyalty/ledger?limit=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_post_sell_requires_trade_feature(self, unused_notify):
        response = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": MAX_SELL_LP,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["side"], "sell")
        self.assertEqual(body["quantity"], MAX_SELL_LP)
        self.assertEqual(body["isk_per_lp"], 800)
        self.assertEqual(body["status"], "open")

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_post_sell_at_max_lp_allowed(self, unused_notify):
        response = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": MAX_SELL_LP,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["quantity"], MAX_SELL_LP)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_post_sell_over_max_lp_rejected(self, unused_notify):
        response = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": MAX_SELL_LP + 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("2,500,000", response.json()["detail"])

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_post_buy_over_max_sell_lp_allowed(self, unused_notify):
        response = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "buy",
                    "quantity": MAX_SELL_LP + 500_000,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["quantity"], MAX_SELL_LP + 500_000)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_post_buy_requires_manage(self, unused_notify):
        denied = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "buy",
                    "quantity": 1_000_000,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(denied.status_code, 403)

        ok = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "buy",
                    "quantity": 1_000_000,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(ok.status_code, 201, ok.content)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    @patch("industry.helpers.lp_buyback_discord.notify_order_claimed")
    @patch("industry.helpers.lp_buyback_discord.notify_order_status_changed")
    def test_claim_and_settle_lifecycle(
        self,
        unused_status_notify,
        unused_claim_notify,
        unused_create_notify,
    ):
        create = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": 500_000,
                    "isk_per_lp": 800,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(create.status_code, 201, create.content)
        order_id = create.json()["id"]

        claim = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps(
                {"destination_character_name": "tactical warfare trading"}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(claim.status_code, 200, claim.content)
        self.assertEqual(claim.json()["status"], "awaiting_lp")
        self.assertEqual(claim.json()["quantity_claimed"], 500_000)
        self.assertEqual(claim.json()["quantity_remaining"], 0)
        self.assertEqual(len(claim.json()["claims"]), 1)
        self.assertEqual(
            claim.json()["destination_character_name"],
            "tactical warfare trading",
        )

        awaiting_isk = self.client.patch(
            f"/api/industry/loyalty/orders/{order_id}",
            data=json.dumps({"status": "awaiting_isk"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(awaiting_isk.status_code, 200)
        self.assertEqual(awaiting_isk.json()["status"], "awaiting_isk")

        completed = self.client.patch(
            f"/api/industry/loyalty/orders/{order_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertIsNotNone(completed.json()["completed_at"])

        entry = IndustryLoyaltyPointLedgerEntry.objects.get(
            market_order_id=order_id
        )
        self.assertEqual(entry.account_id, self.stockpile.pk)
        self.assertEqual(entry.amount, 500_000)
        self.assertEqual(entry.isk_per_lp, 800)
        self.assertEqual(entry.seller_user_id, self.user.pk)
        self.assertEqual(entry.seller_character_name, "LP Seller")
        self.assertEqual(entry.counterparty_user_id, self.manager.pk)
        self.assertEqual(
            entry.counterparty_character_name,
            "tactical warfare trading",
        )
        self.assertEqual(account_balance(self.stockpile), 600_000)

        ledger = self.client.get("/api/industry/loyalty/ledger")
        self.assertEqual(ledger.status_code, 200)
        row = next(r for r in ledger.json() if r["id"] == entry.pk)
        self.assertEqual(row["market_order_id"], order_id)
        self.assertEqual(row["seller_character_name"], "LP Seller")
        self.assertEqual(
            row["counterparty_character_name"],
            "tactical warfare trading",
        )
        self.assertEqual(row["seller_user_id"], self.user.pk)
        self.assertEqual(row["counterparty_user_id"], self.manager.pk)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    @patch("industry.helpers.lp_buyback_discord.notify_order_claimed")
    @patch("industry.helpers.lp_buyback_discord.notify_order_status_changed")
    def test_buy_completion_does_not_post_ledger(
        self,
        unused_status_notify,
        unused_claim_notify,
        unused_create_notify,
    ):
        create = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "buy",
                    "quantity": 250_000,
                    "isk_per_lp": 800,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(create.status_code, 201, create.content)
        order_id = create.json()["id"]

        claim = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps({"destination_character_name": "LP Seller alt"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(claim.status_code, 200, claim.content)
        self.assertEqual(claim.json()["status"], "awaiting_lp")

        for status in ("awaiting_isk", "completed"):
            response = self.client.patch(
                f"/api/industry/loyalty/orders/{order_id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
            )
            self.assertEqual(response.status_code, 200, response.content)

        self.assertFalse(
            IndustryLoyaltyPointLedgerEntry.objects.filter(
                market_order_id=order_id
            ).exists()
        )
        self.assertEqual(account_balance(self.stockpile), 100_000)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    @patch("industry.helpers.lp_buyback_discord.notify_order_claimed")
    @patch("industry.helpers.lp_buyback_discord.notify_order_status_changed")
    def test_partial_claims_until_fully_claimed(
        self,
        unused_status_notify,
        unused_claim_notify,
        unused_create_notify,
    ):
        create = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": 1_000_000,
                    "isk_per_lp": 800,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(create.status_code, 201, create.content)
        order_id = create.json()["id"]

        first = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps(
                {
                    "amount": 400_000,
                    "destination_character_name": "LP Buyer",
                    "destination_corporation_name": "Minmatar Fleet Holdings",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["status"], "open")
        self.assertEqual(first.json()["quantity_claimed"], 400_000)
        self.assertEqual(first.json()["quantity_remaining"], 600_000)
        self.assertEqual(len(first.json()["claims"]), 1)
        self.assertEqual(
            first.json()["claims"][0]["destination_corporation_name"],
            "Minmatar Fleet Holdings",
        )

        over = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps({"amount": 700_000}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(over.status_code, 400)
        self.assertIn("remaining", over.json()["detail"].lower())

        zero = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps({"amount": 0}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(zero.status_code, 400)

        second = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps(
                {
                    "amount": 600_000,
                    "destination_character_name": "tactical warfare trading",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()["status"], "awaiting_lp")
        self.assertEqual(second.json()["quantity_claimed"], 1_000_000)
        self.assertEqual(second.json()["quantity_remaining"], 0)
        self.assertEqual(len(second.json()["claims"]), 2)
        self.assertEqual(
            IndustryLoyaltyPointMarketOrderClaim.objects.filter(
                order_id=order_id
            ).count(),
            2,
        )

        third = self.client.post(
            f"/api/industry/loyalty/orders/{order_id}/claim",
            data=json.dumps({"amount": 1}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.manager_token}",
        )
        self.assertEqual(third.status_code, 400)

    @patch("industry.helpers.lp_buyback_discord.notify_order_created")
    def test_creator_can_cancel_open(self, unused_notify):
        create = self.client.post(
            "/api/industry/loyalty/orders",
            data=json.dumps(
                {
                    "loyalty_point_id": self.currency.pk,
                    "side": "sell",
                    "quantity": 100_000,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        order_id = create.json()["id"]
        cancel = self.client.patch(
            f"/api/industry/loyalty/orders/{order_id}",
            data=json.dumps({"status": "cancelled"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["status"], "cancelled")

    def test_get_orders_defaults_to_active(self):
        open_order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            created_by=self.user,
        )
        IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.COMPLETED,
            created_by=self.user,
        )
        response = self.client.get("/api/industry/loyalty/orders")
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()}
        self.assertIn(open_order.pk, ids)
        self.assertEqual(len(ids), 1)


class LoyaltyBuybackDiscordTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        self.guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=555444333,
            defaults={"name": "LP Buyback Test Guild", "is_active": True},
        )
        self.lp_channel, _ = DiscordChannel.objects.update_or_create(
            channel_id=1189194652511911976,
            defaults={
                "guild": self.guild,
                "name": "lp-buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_lp_buyback": True,
            },
        )
        self.order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=2_500_000,
            isk_per_lp=800,
            created_by=self.user,
        )

    def test_thread_title(self):
        self.assertEqual(order_thread_title(self.order), "WTS 2.5M TLIB @800")

    @patch("industry.helpers.lp_buyback_discord.discord")
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

        notify_order_created(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.discord_thread_id, 555666777)
        discord_mock.create_forum_thread.assert_called_once()
        kwargs = discord_mock.create_forum_thread.call_args.kwargs
        self.assertEqual(kwargs["channel_id"], self.lp_channel.channel_id)
        self.assertIn("WTS 2.5M TLIB @800", kwargs["title"])
        self.assertEqual(kwargs["applied_tags"], ["222"])
        discord_mock.get_channel.assert_called_once_with(
            self.lp_channel.channel_id
        )

    @patch("industry.helpers.lp_buyback_discord.discord")
    def test_notify_order_created_without_forum_tags(self, discord_mock):
        response = MagicMock()
        response.json.return_value = {"id": "555666778"}
        discord_mock.create_forum_thread.return_value = response
        channel_response = MagicMock()
        channel_response.json.return_value = {"available_tags": [], "flags": 0}
        discord_mock.get_channel.return_value = channel_response

        notify_order_created(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.discord_thread_id, 555666778)
        kwargs = discord_mock.create_forum_thread.call_args.kwargs
        self.assertEqual(kwargs["applied_tags"], [])

    @patch("industry.helpers.lp_buyback_discord.discord")
    def test_notify_skips_without_designated_channel(self, discord_mock):
        DiscordChannel.objects.filter(receive_lp_buyback=True).update(
            receive_lp_buyback=False
        )
        notify_order_created(self.order)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.discord_thread_id)
        discord_mock.create_forum_thread.assert_not_called()

    def test_receive_lp_buyback_is_unique(self):
        other = DiscordChannel.objects.create(
            channel_id=999000111,
            guild=self.guild,
            name="lp-buyback-2",
            channel_type=DiscordChannel.FORUM,
            receive_lp_buyback=True,
        )
        self.lp_channel.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.lp_channel.receive_lp_buyback)
        self.assertTrue(other.receive_lp_buyback)


class LpBuybackDiscordButtonsTestCase(AppTestCase):
    def test_custom_id_roundtrip(self):
        self.assertEqual(lp_sent_custom_id(42), "lp_buyback:lp:42")
        self.assertEqual(parse_lp_sent_custom_id("lp_buyback:lp:42"), 42)
        self.assertIsNone(parse_lp_sent_custom_id("lp_buyback:isk:42"))
        self.assertEqual(isk_sent_custom_id(7), "lp_buyback:isk:7")
        self.assertEqual(parse_isk_sent_custom_id("lp_buyback:isk:7"), 7)

    def test_lp_sent_components(self):
        button = lp_sent_components(99)[0]["components"][0]
        self.assertEqual(button["label"], "LP sent")
        self.assertEqual(button["custom_id"], "lp_buyback:lp:99")
        self.assertEqual(button["style"], 3)


class LpBuybackSideAwareMessagingTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        self.seller = self.user
        seller_char = EveCharacter.objects.create(
            character_id=888001,
            character_name="WTS Pilot",
            user=self.seller,
        )
        set_primary_character(self.seller, seller_char)
        DiscordUser.objects.create(
            id=1001, discord_tag="seller#0001", user=self.seller
        )
        self.claimer = User.objects.create(username="wtb_claimer")
        claimer_char = EveCharacter.objects.create(
            character_id=888002,
            character_name="BearThatCares",
            user=self.claimer,
        )
        set_primary_character(self.claimer, claimer_char)
        DiscordUser.objects.create(
            id=1002, discord_tag="bear#0001", user=self.claimer
        )

    def test_wts_awaiting_lp_tags_poster(self):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP,
            created_by=self.seller,
            claimed_by=self.claimer,
            destination_character_name="CT Alt",
        )
        msg = _awaiting_lp_message(order)
        self.assertIn("<@1001>", msg)
        self.assertIn("Send LP to: **CT Alt**", msg)

    def test_wtb_awaiting_lp_tags_claimer(self):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.BUY,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP,
            created_by=self.seller,
            claimed_by=self.claimer,
            destination_character_name="Ballah Inc.",
        )
        msg = _awaiting_lp_message(order)
        self.assertIn("<@1002>", msg)
        self.assertIn("Send LP to: **Ballah Inc.**", msg)

    def test_wtb_awaiting_isk_tags_poster_pay_claimer(self):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.BUY,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.AWAITING_ISK,
            created_by=self.seller,
            claimed_by=self.claimer,
        )
        msg = _awaiting_isk_message(order)
        self.assertIn("<@1001>", msg)
        self.assertIn("Pay ISK to: **BearThatCares**", msg)

    @patch("industry.helpers.lp_buyback_discord.discord")
    def test_awaiting_lp_posts_lp_sent_button(self, discord_mock):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP,
            created_by=self.seller,
            claimed_by=self.claimer,
            destination_character_name="CT Alt",
            discord_thread_id=555,
        )
        notify_order_status_changed(order)
        kwargs = discord_mock.create_message.call_args.kwargs
        self.assertEqual(
            kwargs["payload"]["components"][0]["components"][0]["custom_id"],
            f"lp_buyback:lp:{order.pk}",
        )

    @patch("industry.helpers.lp_buyback_discord.discord")
    def test_completed_closes_thread_without_message(self, discord_mock):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.COMPLETED,
            created_by=self.seller,
            claimed_by=self.claimer,
            discord_thread_id=555,
        )
        notify_order_status_changed(order)
        discord_mock.create_message.assert_not_called()
        discord_mock.close_thread.assert_called_once_with(channel_id=555)

    @patch("industry.helpers.lp_buyback_discord.discord")
    def test_cancelled_closes_thread_without_message(self, discord_mock):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.CANCELLED,
            created_by=self.seller,
            discord_thread_id=777,
        )
        notify_order_status_changed(order)
        discord_mock.create_message.assert_not_called()
        discord_mock.close_thread.assert_called_once_with(channel_id=777)


class LpBuybackDiscordAckApiTestCase(LoyaltyBuybackApiTestCase):
    def setUp(self):
        super().setUp()
        DiscordUser.objects.create(
            id=2001, discord_tag="seller#0001", user=self.user
        )
        DiscordUser.objects.create(
            id=2002, discord_tag="manager#0001", user=self.manager
        )
        self.staff = User.objects.create(username="bot_service", is_staff=True)
        self.staff_token = jwt.encode(
            {"user_id": self.staff.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        self.bystander = User.objects.create(username="bystander")
        DiscordUser.objects.create(
            id=2003, discord_tag="bystander#0001", user=self.bystander
        )

    def _sell_order_awaiting_lp(self):
        return IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=100_000,
            isk_per_lp=800,
            status=IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP,
            created_by=self.user,
            claimed_by=self.manager,
            destination_character_name="CT Alt",
        )

    @patch("industry.helpers.lp_buyback_discord.notify_order_status_changed")
    def test_lp_sent_by_expected_party(self, unused_notify):
        order = self._sell_order_awaiting_lp()
        response = self.client.post(
            f"/api/industry/loyalty/orders/{order.pk}/discord-ack",
            data=json.dumps({"discord_user_id": 2001, "action": "lp_sent"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "awaiting_isk")

    @patch("industry.helpers.lp_buyback_discord.notify_order_status_changed")
    def test_isk_sent_by_manager(self, unused_notify):
        order = self._sell_order_awaiting_lp()
        order.status = IndustryLoyaltyPointMarketOrder.Status.AWAITING_ISK
        order.save(update_fields=["status"])
        response = self.client.post(
            f"/api/industry/loyalty/orders/{order.pk}/discord-ack",
            data=json.dumps({"discord_user_id": 2002, "action": "isk_sent"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "completed")

    def test_wrong_user_rejected(self):
        order = self._sell_order_awaiting_lp()
        response = self.client.post(
            f"/api/industry/loyalty/orders/{order.pk}/discord-ack",
            data=json.dumps({"discord_user_id": 2003, "action": "lp_sent"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_status_rejected(self):
        order = self._sell_order_awaiting_lp()
        response = self.client.post(
            f"/api/industry/loyalty/orders/{order.pk}/discord-ack",
            data=json.dumps({"discord_user_id": 2002, "action": "isk_sent"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.staff_token}",
        )
        self.assertEqual(response.status_code, 400)
