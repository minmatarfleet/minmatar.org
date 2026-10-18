"""
Snapshot of every Discord call the two order-thread mirrors make.

Hangar buyback purchase orders and LP buyback market orders each mirror an
order into a Discord forum thread. They share their thread plumbing; this
test pins the exact client calls (method, arguments, payloads) for both flows
so that sharing it cannot change what Discord receives. The snapshot lives in
test_order_thread_parity.json. To update it on purpose, run with
UPDATE_ORDER_THREAD_SNAPSHOT=1 and review the diff.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase, override_settings

from buyback.helpers import purchase_discord
from buyback.models import BuybackPurchaseOrder, SellPriceBasis
from buyback.tests.helpers import ensure_type
from discord.models import DiscordChannel, DiscordGuild, DiscordUser
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from industry.helpers import lp_buyback_discord
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

SNAPSHOT = Path(__file__).with_suffix(".json")
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc)


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


def _recorder(tags: list[dict], thread_id: int) -> MagicMock:
    client = MagicMock()
    client.get_channel.return_value = _response({"available_tags": tags})
    client.create_forum_thread.return_value = _response({"id": str(thread_id)})
    return client


def _calls(client: MagicMock) -> list:
    """Client method calls as JSON-able [name, args, kwargs]."""
    out = []
    for name, args, kwargs in client.mock_calls:
        if "(" in name or "." in name:
            continue  # calls on returned responses, e.g. get_channel().json()
        out.append([name, list(args), dict(sorted(kwargs.items()))])
    return json.loads(json.dumps(out, default=str))


@override_settings(
    WEB_LINK_URL="https://my.minmatar.org", DISCORD_GUILD_ID="555444333"
)
@patch("time.sleep")
class OrderThreadParityTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=555444333,
            defaults={"name": "Parity Guild", "is_active": True},
        )
        DiscordChannel.objects.update_or_create(
            channel_id=7001,
            defaults={
                "guild": guild,
                "name": "buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_buyback": True,
            },
        )
        DiscordChannel.objects.update_or_create(
            channel_id=7002,
            defaults={
                "guild": guild,
                "name": "lp-buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_lp_buyback": True,
            },
        )
        DiscordChannel.objects.update_or_create(
            channel_id=7003,
            defaults={
                "guild": guild,
                "name": "conversion",
                "channel_type": DiscordChannel.TEXT,
                "receive_lp_conversion_alerts": True,
            },
        )
        self.seller = self._user(91001, "seller", 1001, 880001, "WTS Pilot")
        self.buyer = self._user(91002, "buyer", 1002, 880002, "WTB Pilot")
        self.staff = self._user(91003, "staff", 1003, 880003, "Desk Pilot")
        self.results = {}

    def _user(self, pk, username, discord_id, character_id, name):
        user = User.objects.create(pk=pk, username=username)
        DiscordUser.objects.create(
            id=discord_id, discord_tag=f"{username}#0001", user=user
        )
        character = EveCharacter.objects.create(
            character_id=character_id, character_name=name, user=user
        )
        set_primary_character(user, character)
        return user

    def _buyback_order(self, pk: int = 4242) -> BuybackPurchaseOrder:
        ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        order = BuybackPurchaseOrder.objects.create(
            pk=pk,
            created_by=self.seller,
            character_name="WTS Pilot",
            paste="Compressed Veldspar\t10",
            contract_total=3_500_000,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        order.lines.create(
            eve_type=ore,
            name=ore.name,
            quantity=10,
            unit_price=Decimal("350000.00"),
            line_total=Decimal("3500000.00"),
        )
        return order

    def _lp_order(self, **fields) -> IndustryLoyaltyPointMarketOrder:
        currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=1000182,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        values = {
            "pk": 5151,
            "loyalty_point": currency,
            "side": IndustryLoyaltyPointMarketOrder.Side.SELL,
            "quantity": 1_000_000,
            "isk_per_lp": 800,
            "created_by": self.seller,
            "notes": "Fast please",
        }
        values.update(fields)
        return IndustryLoyaltyPointMarketOrder.objects.create(**values)

    def _run(self, name, module, client, fn):
        with patch.object(module, "discord", client):
            fn()
        self.results[name] = _calls(client)

    def test_discord_calls_match_snapshot(self, unused_sleep):
        # --- Hangar buyback purchase orders -----------------------------
        order = self._buyback_order()
        client = _recorder(
            [{"id": "111", "name": "misc"}, {"id": "222", "name": "Open"}],
            9001,
        )
        self._run(
            "buyback.created",
            purchase_discord,
            client,
            lambda: purchase_discord.notify_purchase_created(order),
        )
        order.refresh_from_db()
        self.assertEqual(9001, order.discord_thread_id)

        order.status = BuybackPurchaseOrder.Status.COMPLETED
        order.completed_by = self.staff
        self._run(
            "buyback.completed",
            purchase_discord,
            _recorder([], 0),
            lambda: purchase_discord.notify_purchase_status_changed(order),
        )
        order.status = BuybackPurchaseOrder.Status.CANCELLED
        self._run(
            "buyback.cancelled",
            purchase_discord,
            _recorder([], 0),
            lambda: purchase_discord.notify_purchase_status_changed(order),
        )
        no_tags = _recorder([], 9002)
        other = self._buyback_order(pk=4243)
        self._run(
            "buyback.created_without_tags",
            purchase_discord,
            no_tags,
            lambda: purchase_discord.notify_purchase_created(other),
        )

        # --- LP buyback market orders -----------------------------------
        lp = self._lp_order()
        self._run(
            "lp.created",
            lp_buyback_discord,
            _recorder(
                [{"id": "331", "name": "misc"}, {"id": "333", "name": "WTS"}],
                9101,
            ),
            lambda: lp_buyback_discord.notify_order_created(lp),
        )
        lp.refresh_from_db()
        self.assertEqual(9101, lp.discord_thread_id)

        lp.status = IndustryLoyaltyPointMarketOrder.Status.CLAIMED
        lp.claimed_by = self.buyer
        lp.save()
        claim = IndustryLoyaltyPointMarketOrderClaim.objects.create(
            order=lp,
            amount=400_000,
            destination_character_name="WTB Alt",
            claimed_by=self.buyer,
        )
        self._run(
            "lp.claimed",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.notify_order_claimed(lp, claim=claim),
        )
        self._run(
            "lp.claims_released",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.notify_order_claims_released(
                lp, released_by=self.buyer, released_amount=400_000
            ),
        )
        for status in ("AWAITING_LP", "AWAITING_ISK", "COMPLETED"):
            lp.status = getattr(IndustryLoyaltyPointMarketOrder.Status, status)
            self._run(
                f"lp.status.{status.lower()}",
                lp_buyback_discord,
                _recorder([], 0),
                lambda: lp_buyback_discord.notify_order_status_changed(lp),
            )
        lp.status = IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP
        self._run(
            "lp.stalled_reminder",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.post_stalled_reminder(
                lp, waited_hours=24, cancel_at=NOW + timedelta(hours=24)
            ),
        )
        self._run(
            "lp.cancelled",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.notify_order_cancelled(
                lp, cancelled_by=self.buyer, reason="Changed my mind."
            ),
        )
        self._run(
            "lp.close_by_id",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.close_lp_buyback_thread_id(9101),
        )
        lp.status_changed_at = NOW - timedelta(days=8)
        self._run(
            "lp.stale_digest",
            lp_buyback_discord,
            _recorder([], 0),
            lambda: lp_buyback_discord.post_stale_open_orders_digest(
                [lp], now=NOW
            ),
        )

        if os.environ.get("UPDATE_ORDER_THREAD_SNAPSHOT"):
            SNAPSHOT.write_text(
                json.dumps(self.results, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(sorted(expected), sorted(self.results))
        for name, calls in expected.items():
            self.assertEqual(calls, self.results[name], name)
