"""Reposting the Awaiting LP update that a claim lost before commit."""

import importlib
from unittest.mock import patch

from django.apps import apps as django_apps
from django.test import override_settings

from app.test import TestCase as AppTestCase
from industry.helpers.lp_buyback_discord import repost_missing_awaiting_lp
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
)

DISCORD = "industry.helpers.lp_buyback_discord.discord"
THREAD_ID = 4242
STARTER = {"id": str(THREAD_ID), "content": "**Sell** 1,000 ... Status: Open"}

migration = importlib.import_module(
    "industry.migrations.0057_repost_missing_lp_buyback_awaiting_lp"
)


class RepostMissingAwaitingLpTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=1000182,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 700,
                "is_active": True,
            },
        )

    def _order(self, status, thread_id=THREAD_ID):
        return IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=self.currency,
            side=IndustryLoyaltyPointMarketOrder.Side.SELL,
            quantity=1000,
            isk_per_lp=700,
            status=status,
            created_by=self.user,
            claimed_by=self.user,
            destination_character_name="Claim Corp",
            discord_thread_id=thread_id,
        )

    def test_posts_when_the_thread_has_only_the_starter(self):
        order = self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP)
        with patch(DISCORD) as discord:
            discord.get_messages.return_value = [STARTER]
            self.assertTrue(repost_missing_awaiting_lp(order.pk))
        discord.create_message.assert_called_once()
        kwargs = discord.create_message.call_args.kwargs
        self.assertEqual(kwargs["channel_id"], THREAD_ID)
        self.assertIn("Awaiting LP transfer", kwargs["payload"]["content"])
        self.assertIn("components", kwargs["payload"])

    def test_skips_when_awaiting_lp_was_already_posted(self):
        order = self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP)
        with patch(DISCORD) as discord:
            discord.get_messages.return_value = [
                {"content": "\n:package: Awaiting LP transfer\nClaimed by x"},
                STARTER,
            ]
            self.assertFalse(repost_missing_awaiting_lp(order.pk))
        discord.create_message.assert_not_called()

    def test_posts_when_the_last_awaiting_post_was_before_a_release(self):
        order = self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP)
        with patch(DISCORD) as discord:
            discord.get_messages.return_value = [
                {"content": ":arrows_counterclockwise: Claim released by x"},
                {"content": ":package: Awaiting LP transfer"},
                STARTER,
            ]
            self.assertTrue(repost_missing_awaiting_lp(order.pk))
        discord.create_message.assert_called_once()

    def test_skips_when_the_thread_cannot_be_read(self):
        order = self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP)
        with patch(DISCORD) as discord:
            discord.get_messages.side_effect = RuntimeError("403")
            self.assertFalse(repost_missing_awaiting_lp(order.pk))
        discord.create_message.assert_not_called()

    def test_skips_orders_no_longer_waiting_on_lp(self):
        order = self._order(
            IndustryLoyaltyPointMarketOrder.Status.AWAITING_ISK
        )
        with patch(DISCORD) as discord:
            self.assertFalse(repost_missing_awaiting_lp(order.pk))
            self.assertFalse(repost_missing_awaiting_lp(order.pk + 999))
        discord.get_messages.assert_not_called()
        discord.create_message.assert_not_called()

    def test_migration_queues_only_awaiting_lp_orders_with_a_thread(self):
        waiting = self._order(
            IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP
        )
        self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP, None)
        self._order(IndustryLoyaltyPointMarketOrder.Status.OPEN)
        with patch("app.celery.app.signature") as signature, override_settings(
            TESTING=False
        ):
            migration.queue_reposts(django_apps, None)
        signature.assert_called_once_with(
            "industry.tasks.repost_missing_lp_buyback_awaiting_lp_task",
            args=[waiting.pk],
        )
        signature.return_value.apply_async.assert_called_once_with(
            countdown=migration.REPOST_DELAY_SECONDS
        )

    def test_migration_does_nothing_under_tests(self):
        self._order(IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP)
        with patch("app.celery.app.signature") as signature:
            migration.queue_reposts(django_apps, None)
        signature.assert_not_called()
