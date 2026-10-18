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
from industry.tasks import close_lp_buyback_discord_thread_task
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

TLIB_CORP_ID = 1000182
CHANNEL_ID = 1189194652511911976
CONVERSION_CHANNEL_ID = 1174103016161427556
Status = IndustryLoyaltyPointMarketOrder.Status


@patch.object(
    close_lp_buyback_discord_thread_task,
    "apply_async",
    wraps=close_lp_buyback_discord_thread_task.apply_async,
)
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

    def _order(
        self,
        status,
        *,
        waited_hours,
        thread_id=777,
        reminded=None,
        side=IndustryLoyaltyPointMarketOrder.Side.SELL,
    ):
        # WTS: a pilot posts, the Conversion Team claims. WTB: the
        # Conversion Team posts, a pilot claims and sends the LP.
        is_sell = side == IndustryLoyaltyPointMarketOrder.Side.SELL
        poster, claimer = (
            (self.seller, self.buyer) if is_sell else (self.buyer, self.seller)
        )
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=side,
            quantity=100_000,
            isk_per_lp=700,
            status=status,
            created_by=poster,
            claimed_by=None if status == Status.OPEN else claimer,
            destination_character_name="Alliance Buyer",
            discord_thread_id=thread_id,
        )
        if status != Status.OPEN:
            IndustryLoyaltyPointMarketOrderClaim.objects.create(
                order=order,
                amount=100_000,
                destination_character_name="Alliance Buyer",
                claimed_by=claimer,
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
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, unused_close_later
    ):
        order = self._order(Status.OPEN, waited_hours=0, thread_id=None)
        self._sweep(discord_mock, client_cls)
        discord_mock.create_forum_thread.assert_not_called()
        order.refresh_from_db()
        self.assertIsNone(order.discord_thread_id)

    def test_closes_threads_left_open_for_finished_orders(
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, unused_close_later
    ):
        order = self._order(Status.OPEN, waited_hours=200)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["reminded"], stats["cancelled"]), (0, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.OPEN)

    def test_no_reminder_before_24h(
        self, discord_mock, client_cls, unused_close_later
    ):
        self._order(Status.AWAITING_LP, waited_hours=23)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["reminded"], 0)
        discord_mock.create_message.assert_not_called()

    def test_awaiting_lp_reminds_seller_at_24h(
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, close_later
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
        # Archived a few seconds later by a task, not a time.sleep.
        close_later.assert_called_once_with(args=[777], countdown=5)
        discord_mock.close_thread.assert_called_once_with(channel_id=777)

    def test_long_stalled_order_gets_a_days_warning_first(
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, unused_close_later
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
        self, discord_mock, client_cls, unused_close_later
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

    def test_claimer_stalling_lp_is_pestered_daily_never_cancelled(
        self, discord_mock, client_cls, unused_close_later
    ):
        # WTB awaiting LP: the claiming pilot owes the LP, not the poster.
        order = self._order(
            Status.AWAITING_LP,
            waited_hours=25,
            side=IndustryLoyaltyPointMarketOrder.Side.BUY,
        )
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["reminded"], 1)
        content = self._posted(discord_mock)[0]
        self.assertTrue(content.startswith("<@2001>"))
        self.assertNotIn("cancelled automatically", content)

        for _ in range(3):
            self.now += timedelta(hours=24)
            stats = self._sweep(discord_mock, client_cls)
            self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.AWAITING_LP)

    def test_claimed_waiting_on_claimer_is_never_cancelled(
        self, discord_mock, client_cls, unused_close_later
    ):
        order = self._order(
            Status.CLAIMED,
            waited_hours=24 * 5,
            reminded=self.now - timedelta(hours=30),
        )
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        self.assertTrue(self._posted(discord_mock)[0].startswith("<@2002>"))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.CLAIMED)

    def _enable_conversion_alerts(self):
        DiscordChannel.objects.update_or_create(
            channel_id=CONVERSION_CHANNEL_ID,
            defaults={
                "guild": DiscordGuild.objects.get(guild_id=555444333),
                "name": "conversion",
                "channel_type": DiscordChannel.TEXT,
                "receive_lp_conversion_alerts": True,
            },
        )

    def _digests(self, discord_mock) -> list[str]:
        return [
            c.kwargs["payload"]["content"]
            for c in discord_mock.create_message.call_args_list
            if c.kwargs["channel_id"] == CONVERSION_CHANNEL_ID
        ]

    def test_week_old_open_orders_flagged_weekly(
        self, discord_mock, client_cls, unused_close_later
    ):
        self._enable_conversion_alerts()
        self._order(Status.OPEN, waited_hours=24 * 8, thread_id=901)
        self._order(Status.OPEN, waited_hours=24 * 6, thread_id=902)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["stale_open_flagged"], 1)
        digests = self._digests(discord_mock)
        self.assertEqual(len(digests), 1)
        self.assertIn("**1 LP buyback order** open for a week", digests[0])
        self.assertIn(
            "**WTS 100K TLIB @700** by Slow Seller — 8d, 100,000 LP "
            "unclaimed · <#901>",
            digests[0],
        )
        self.assertNotIn("<#902>", digests[0])

        self.now += timedelta(days=1)
        stats = self._sweep(discord_mock, client_cls)
        # The 6-day order has now crossed a week; the 8-day one waits a week.
        self.assertEqual(stats["stale_open_flagged"], 1)
        self.assertIn("<#902>", self._digests(discord_mock)[-1])
        self.assertNotIn("<#901>", self._digests(discord_mock)[-1])

        self.now += timedelta(days=6)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual(stats["stale_open_flagged"], 1)
        self.assertIn("<#901>", self._digests(discord_mock)[-1])

    def test_failed_digest_retries_next_sweep(
        self, discord_mock, client_cls, unused_close_later
    ):
        self._enable_conversion_alerts()
        order = self._order(Status.OPEN, waited_hours=24 * 8)
        discord_mock.create_message.side_effect = RuntimeError("discord down")
        self.assertEqual(
            self._sweep(discord_mock, client_cls)["stale_open_flagged"], 0
        )
        order.refresh_from_db()
        self.assertIsNone(order.stalled_reminder_at)
        discord_mock.create_message.side_effect = None
        self.assertEqual(
            self._sweep(discord_mock, client_cls)["stale_open_flagged"], 1
        )

    def test_undelivered_reminder_does_not_arm_auto_cancel(
        self, discord_mock, client_cls, unused_close_later
    ):
        order = self._order(Status.AWAITING_LP, waited_hours=30)
        discord_mock.create_message.side_effect = RuntimeError("discord 503")
        self.assertEqual(self._sweep(discord_mock, client_cls)["reminded"], 0)
        order.refresh_from_db()
        self.assertIsNone(order.stalled_reminder_at)

        # Discord recovers a day later: the seller is warned now, and the
        # cancel is still a full day out.
        discord_mock.create_message.side_effect = None
        self.now += timedelta(hours=24)
        stats = self._sweep(discord_mock, client_cls)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.AWAITING_LP)

    def test_order_without_thread_is_not_reminded_or_cancelled(
        self, discord_mock, client_cls, unused_close_later
    ):
        discord_mock.create_forum_thread.side_effect = RuntimeError("down")
        order = self._order(
            Status.AWAITING_LP, waited_hours=24 * 5, thread_id=None
        )
        for _ in range(3):
            stats = self._sweep(discord_mock, client_cls)
            self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 0))
            self.now += timedelta(hours=24)
        order.refresh_from_db()
        self.assertEqual(order.status, Status.AWAITING_LP)
        self.assertIsNone(order.stalled_reminder_at)
