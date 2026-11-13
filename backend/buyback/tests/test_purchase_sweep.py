"""Hourly hangar-sale sweep: reminders, auto-cancel, thread mirror."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.utils import timezone

from app.test import TestCase
from buyback.discord_tasks import close_buyback_purchase_thread_task
from buyback.helpers.purchase_orders import mark_contract_up
from buyback.helpers.purchase_sweep import sweep_buyback_purchase_orders
from buyback.models import (
    BuybackPurchaseOrder,
    EveBuybackSettings,
    SellPriceBasis,
)
from discord.models import DiscordChannel, DiscordGuild, DiscordUser

CHANNEL_ID = 1542652883026186320
Status = BuybackPurchaseOrder.Status
Step = BuybackPurchaseOrder.SettlementStep


@patch.object(
    close_buyback_purchase_thread_task,
    "apply_async",
    wraps=close_buyback_purchase_thread_task.apply_async,
)
@patch("buyback.helpers.purchase_discord.DiscordClient")
@patch("buyback.helpers.purchase_discord.discord")
class PurchaseSweepTestCase(TestCase):
    def setUp(self):
        super().setUp()
        guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=555444333,
            defaults={"name": "Buyback Test Guild", "is_active": True},
        )
        DiscordChannel.objects.update_or_create(
            channel_id=CHANNEL_ID,
            defaults={
                "guild": guild,
                "name": "buyback",
                "channel_type": DiscordChannel.FORUM,
                "receive_buyback": True,
            },
        )
        DiscordUser.objects.create(
            id=4242, discord_tag="buyer#0001", user=self.user
        )
        self.coordinator = User.objects.create(username="sale_coordinator")
        DiscordUser.objects.create(
            id=9001, discord_tag="coord#0001", user=self.coordinator
        )
        EveBuybackSettings.load().coordinators.add(self.coordinator)
        self.now = timezone.now()

    def _order(
        self,
        *,
        waited_hours,
        thread_id=777,
        reminded=None,
        step=Step.CONTRACT_UP,
        status=Status.PENDING,
    ):
        order = BuybackPurchaseOrder.objects.create(
            created_by=self.user,
            character_name="Test Pilot",
            paste="Veldspar",
            contract_total=1_000_000,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
            status=status,
            settlement_step=step,
            discord_thread_id=thread_id,
        )
        when = self.now - timedelta(hours=waited_hours)
        BuybackPurchaseOrder.objects.filter(pk=order.pk).update(
            created_at=when,
            settlement_changed_at=when,
            stalled_reminder_at=reminded,
        )
        return BuybackPurchaseOrder.objects.get(pk=order.pk)

    def _sweep(self, discord_mock, client_cls, unused_close, active_ids=()):
        channel = MagicMock()
        channel.json.return_value = {"available_tags": [], "flags": 0}
        discord_mock.get_channel.return_value = channel
        client_cls.return_value.get_active_threads.return_value.json.return_value = {
            "threads": [
                {"id": str(thread_id), "parent_id": str(CHANNEL_ID)}
                for thread_id in active_ids
            ]
        }
        return sweep_buyback_purchase_orders(now=self.now)

    def _posted(self, discord_mock) -> list[str]:
        return [
            call.kwargs["payload"]["content"]
            for call in discord_mock.create_message.call_args_list
        ]

    def test_no_reminder_before_24h(
        self, discord_mock, client_cls, unused_close
    ):
        self._order(waited_hours=23)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["reminded"], stats["cancelled"]), (0, 0))
        discord_mock.create_message.assert_not_called()

    def test_contract_up_reminder_warns_then_stops(
        self, discord_mock, client_cls, unused_close
    ):
        order = self._order(waited_hours=25)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual(stats["reminded"], 1)
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        content = payload["content"]
        self.assertIn("<@9001>", content)
        self.assertIn("<@4242>", content)
        self.assertIn("put the contract up", content)
        self.assertIn("for 25 hours", content)
        cancel_at = int((self.now + timedelta(hours=24)).timestamp())
        self.assertIn(f"<t:{cancel_at}:R>", content)
        self.assertEqual(
            payload["components"][0]["components"][0]["label"], "Contract up"
        )
        order.refresh_from_db()
        self.assertEqual(order.stalled_reminder_at, self.now)

        discord_mock.create_message.reset_mock()
        self.assertEqual(
            self._sweep(discord_mock, client_cls, unused_close)["reminded"], 0
        )
        discord_mock.create_message.assert_not_called()

    def test_long_stalled_sale_gets_a_days_warning_first(
        self, discord_mock, client_cls, unused_close
    ):
        order = self._order(waited_hours=24 * 9)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        cancel_at = int((self.now + timedelta(hours=24)).timestamp())
        self.assertIn(f"<t:{cancel_at}:R>", self._posted(discord_mock)[0])

        self.now += timedelta(hours=23)
        self.assertEqual(
            self._sweep(discord_mock, client_cls, unused_close)["cancelled"], 0
        )
        self.now += timedelta(hours=1)
        self.assertEqual(
            self._sweep(discord_mock, client_cls, unused_close)["cancelled"], 1
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Status.CANCELLED)

    def test_auto_cancels_after_48h_and_announces_reason(
        self, discord_mock, client_cls, close_later
    ):
        order = self._order(
            waited_hours=49, reminded=self.now - timedelta(hours=25)
        )
        stats = self._sweep(discord_mock, client_cls, close_later)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (1, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.CANCELLED)
        content = self._posted(discord_mock)[-1]
        self.assertIn("<@9001>", content)
        self.assertIn("<@4242>", content)
        self.assertIn("Sale cancelled", content)
        self.assertIn("No progress for 48 hours", content)
        self.assertIn("Test Pilot", content)
        close_later.assert_called_once_with(args=[777], countdown=5)

    def test_contract_up_resets_the_clock(
        self, discord_mock, client_cls, unused_close
    ):
        order = self._order(
            waited_hours=49, reminded=self.now - timedelta(hours=25)
        )
        mark_contract_up(order)
        order.refresh_from_db()
        self.assertEqual(order.settlement_step, Step.AWAITING_ACCEPT)
        self.assertIsNone(order.stalled_reminder_at)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.PENDING)

    def test_awaiting_accept_is_reminded_daily_never_cancelled(
        self, discord_mock, client_cls, unused_close
    ):
        order = self._order(
            waited_hours=72,
            reminded=self.now - timedelta(hours=12),
            step=Step.AWAITING_ACCEPT,
        )
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 0))

        self.now += timedelta(hours=12)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        payload = discord_mock.create_message.call_args.kwargs["payload"]
        self.assertTrue(payload["content"].startswith("<@4242>"))
        self.assertIn("accept the contract", payload["content"])
        self.assertNotIn("cancelled automatically", payload["content"])
        self.assertEqual(
            payload["components"][0]["components"][0]["label"],
            "Contract accepted",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Status.PENDING)

    def test_creates_missing_thread_after_grace(
        self, discord_mock, client_cls, unused_close
    ):
        fresh = self._order(waited_hours=0, thread_id=None)
        self._sweep(discord_mock, client_cls, unused_close)
        discord_mock.create_forum_thread.assert_not_called()
        fresh.refresh_from_db()
        self.assertIsNone(fresh.discord_thread_id)

        order = self._order(waited_hours=1, thread_id=None)
        response = MagicMock()
        response.json.return_value = {"id": "123456"}
        discord_mock.create_forum_thread.return_value = response
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual(stats["threads_created"], 1)
        order.refresh_from_db()
        self.assertEqual(order.discord_thread_id, 123456)

    def test_closes_threads_left_open_for_finished_sales(
        self, discord_mock, client_cls, unused_close
    ):
        self._order(waited_hours=1, thread_id=901, status=Status.COMPLETED)
        self._order(waited_hours=1, thread_id=902)
        stats = self._sweep(
            discord_mock,
            client_cls,
            unused_close,
            active_ids=(901, 902, 1533601193454997554),
        )
        self.assertEqual(stats["threads_closed"], 1)
        discord_mock.close_thread.assert_called_once_with(channel_id=901)

    def test_undelivered_reminder_does_not_arm_auto_cancel(
        self, discord_mock, client_cls, unused_close
    ):
        order = self._order(waited_hours=30)
        discord_mock.create_message.side_effect = RuntimeError("discord 503")
        self.assertEqual(
            self._sweep(discord_mock, client_cls, unused_close)["reminded"], 0
        )
        order.refresh_from_db()
        self.assertIsNone(order.stalled_reminder_at)

        discord_mock.create_message.side_effect = None
        self.now += timedelta(hours=24)
        stats = self._sweep(discord_mock, client_cls, unused_close)
        self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 1))
        order.refresh_from_db()
        self.assertEqual(order.status, Status.PENDING)

    def test_sale_without_a_thread_is_not_cancelled(
        self, discord_mock, client_cls, unused_close
    ):
        discord_mock.create_forum_thread.side_effect = RuntimeError("down")
        order = self._order(waited_hours=24 * 5, thread_id=None)
        for _ in range(3):
            stats = self._sweep(discord_mock, client_cls, unused_close)
            self.assertEqual((stats["cancelled"], stats["reminded"]), (0, 0))
            self.now += timedelta(hours=24)
        order.refresh_from_db()
        self.assertEqual(order.status, Status.PENDING)
