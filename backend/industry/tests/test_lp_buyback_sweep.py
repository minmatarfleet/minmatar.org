"""Tests for the hourly LP buyback sweep (threads, reminders, auto-cancel)."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.utils import timezone

from app.test import TestCase as AppTestCase
from discord.models import DiscordChannel, DiscordGuild, DiscordUser
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from industry.helpers.lp_buyback_sweep import sweep_lp_buyback_orders
from industry.helpers.lp_market_orders import auto_cancel_stalled_order
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

TLIB_CORP_ID = 1000182
CHANNEL_ID = 1189194652511911976
Status = IndustryLoyaltyPointMarketOrder.Status


@patch("industry.helpers.lp_buyback_discord.time.sleep")
@patch("industry.helpers.lp_buyback_discord.DiscordClient")
@patch("industry.helpers.lp_buyback_discord.discord")
class LpBuybackSweepTestCase(AppTestCase):
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
                "default_isk_per_lp": 700,
                "is_active": True,
            },
        )
        guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=555444333,
            defaults={"name": "LP Buyback Test Guild", "is_active": True},
        )
        DiscordChannel.objects.update_or_create(
            channel_id=CHANNEL_ID,
            defaults={
                "guild": guild,
                "name": "lp-buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_lp_buyback": True,
            },
        )
        self.seller = self.user
        set_primary_character(
            self.seller,
            EveCharacter.objects.create(
                character_id=889001,
                character_name="Slow Seller",
                user=self.seller,
            ),
        )
        DiscordUser.objects.create(
            id=2001, discord_tag="seller#0001", user=self.seller
        )
        self.buyer = User.objects.create(username="lp_buyer")
        set_primary_character(
            self.buyer,
            EveCharacter.objects.create(
                character_id=889002,
                character_name="Alliance Buyer",
                user=self.buyer,
            ),
        )
        DiscordUser.objects.create(
            id=2002, discord_tag="buyer#0001", user=self.buyer
        )
        self.now = timezone.now()

    def _order(self, status, *, waited_hours, thread_id=777, reminded=None):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=100_000,
            isk_per_lp=700,
            status=status,
            created_by=self.seller,
            claimed_by=None if status == Status.OPEN else self.buyer,
            destination_character_name="Alliance Buyer",
            discord_thread_id=thread_id,
        )
        if status != Status.OPEN:
            IndustryLoyaltyPointMarketOrderClaim.objects.create(
                order=order,
                amount=100_000,
                destination_character_name="Alliance Buyer",
                claimed_by=self.buyer,
            )
        IndustryLoyaltyPointMarketOrder.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=waited_hours),
            status_changed_at=self.now - timedelta(hours=waited_hours),
            stalled_reminder_at=reminded,
        )
        return IndustryLoyaltyPointMarketOrder.objects.get(pk=order.pk)

    def _sweep(self, discord_mock, client_cls, active_ids=()):
        client_cls.return_value.get_active_threads.return_value.json.return_value = {
            "threads": [
                {"id": str(thread_id), "parent_id": str(CHANNEL_ID)}
                for thread_id in active_ids
            ]
        }
        with self.captureOnCommitCallbacks(execute=True):
            return sweep_lp_buyback_orders(now=self.now)

    def _posted(self, discord_mock) -> list[str]:
        return [
            c.kwargs["payload"]["content"]
            for c in discord_mock.create_message.call_args_list
        ]

    def test_creates_missing_thread_for_active_order(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(Status.OPEN, waited_hours=1, thread_id=None)
        response = MagicMock()
        response.json.return_value = {"id": "123456"}
        discord_mock.create_forum_thread.return_value = response
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["threads_created"], 1)
        order.refresh_from_db()
        self.assertEqual(order.discord_thread_id, 123456)

    def test_brand_new_order_gets_grace_before_retry(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(Status.OPEN, waited_hours=0, thread_id=None)
        self._sweep(discord_mock, client_cls)
        discord_mock.create_forum_thread.assert_not_called()
        order.refresh_from_db()
        self.assertIsNone(order.discord_thread_id)

    def test_closes_threads_left_open_for_finished_orders(
        self, discord_mock, client_cls, unused_sleep
    ):
        self._order(Status.COMPLETED, waited_hours=1, thread_id=901)
        self._order(Status.OPEN, waited_hours=1, thread_id=902)
        guide_thread = 1533601193454997554
        stats = self._sweep(
            discord_mock, client_cls, active_ids=(901, 902, guide_thread)
        )
        self.assertEqual(stats["threads_closed"], 1)
        discord_mock.close_thread.assert_called_once_with(channel_id=901)

    def test_open_orders_are_never_reminded_or_cancelled(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(Status.OPEN, waited_hours=200)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["reminded"], stats["cancelled"]), (0, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.OPEN)

    def test_no_reminder_before_24h(
        self, discord_mock, client_cls, unused_sleep
    ):
        self._order(Status.AWAITING_LP, waited_hours=23)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["reminded"], 0)
        discord_mock.create_message.assert_not_called()

    def test_awaiting_lp_reminds_seller_at_24h(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(Status.AWAITING_LP, waited_hours=25)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["reminded"], 1)
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        content = payload["content"]
        self.assertTrue(content.startswith("<@2001>"))
        self.assertIn("send LP to **Alliance Buyer**", content)
        self.assertIn("for 25 hours", content)
        # 48h from the status change, but never less than a day's warning.
        cancel_at = int((self.now + timedelta(hours=24)).timestamp())
        self.assertIn(f"<t:{cancel_at}:R>", content)
        self.assertEqual(
            payload["components"][0]["components"][0]["label"], "LP sent"
        )
        order.refresh_from_db()
        self.assertEqual(order.stalled_reminder_at, self.now)

        # A second sweep in the same window does not ping again.
        discord_mock.create_message.reset_mock()
        self.assertEqual(self._sweep(discord_mock, client_cls)["reminded"], 0)
        discord_mock.create_message.assert_not_called()

    def test_auto_cancels_after_48h_and_announces_reason(
        self, discord_mock, client_cls, sleep_mock
    ):
        order = self._order(
            Status.AWAITING_LP,
            waited_hours=49,
            reminded=self.now - timedelta(hours=25),
        )
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (1, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.CANCELLED)
        content = self._posted(discord_mock)[-1]
        self.assertIn("<@2001> <@2002>", content)
        self.assertIn(":x: Order cancelled\n", content)
        self.assertIn(
            "No progress for 48 hours while waiting on **Slow Seller** to "
            "send LP to **Alliance Buyer**",
            content,
        )
        sleep_mock.assert_called_once_with(5)
        discord_mock.close_thread.assert_called_once_with(channel_id=777)

    def test_long_stalled_order_gets_a_days_warning_first(
        self, discord_mock, client_cls, unused_sleep
    ):
        # Orders already stalled for days when the sweep first ships are
        # warned, not cancelled outright.
        order = self._order(Status.AWAITING_LP, waited_hours=24 * 9)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        cancel_at = int((self.now + timedelta(hours=24)).timestamp())
        self.assertIn(f"<t:{cancel_at}:R>", self._posted(discord_mock)[0])

        self.now += timedelta(hours=23)
        self.assertEqual(self._sweep(discord_mock, client_cls)["cancelled"], 0)
        self.now += timedelta(hours=1)
        self.assertEqual(self._sweep(discord_mock, client_cls)["cancelled"], 1)
        order.refresh_from_db()
        self.assertEqual(order.status, Status.CANCELLED)

    def test_awaiting_isk_is_reminded_daily_never_cancelled(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(
            Status.AWAITING_ISK,
            waited_hours=72,
            reminded=self.now - timedelta(hours=12),
        )
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 0))

        self.now += timedelta(hours=12)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        self.assertTrue(payload["content"].startswith("<@2002>"))
        self.assertIn("pay **70,000,000 ISK**", payload["content"])
        self.assertNotIn("cancelled automatically", payload["content"])
        self.assertEqual(
            payload["components"][0]["components"][0]["label"], "ISK sent"
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Status.AWAITING_ISK)

    def test_progress_resets_the_clock(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(
            Status.AWAITING_LP,
            waited_hours=30,
            reminded=self.now - timedelta(hours=6),
        )
        order.status = Status.AWAITING_ISK
        order.save()
        order.refresh_from_db()
        self.assertIsNone(order.stalled_reminder_at)
        self.assertEqual(self._sweep(discord_mock, client_cls)["reminded"], 0)

    def test_auto_cancel_skips_order_that_moved_on(
        self, discord_mock, client_cls, unused_sleep
    ):
        order = self._order(Status.AWAITING_ISK, waited_hours=60)
        self.assertFalse(
            auto_cancel_stalled_order(
                order.pk,
                stalled_before=self.now - timedelta(hours=48),
                reason="x",
            )
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Status.AWAITING_ISK)
