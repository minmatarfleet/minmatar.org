from django.contrib.auth.models import User
from django.test import TestCase

from discord.models import DiscordUser
from notifications.ack import AckError, ack_delivery_for_discord_user
from notifications.discord_buttons import (
    ack_custom_id,
    mark_as_read_components,
    parse_ack_custom_id,
)
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
)


class DiscordButtonsTestCase(TestCase):
    def test_ack_custom_id_roundtrip(self):
        self.assertEqual(ack_custom_id(42), "notif_ack:42")
        self.assertEqual(parse_ack_custom_id("notif_ack:42"), 42)
        self.assertIsNone(parse_ack_custom_id("notif_ack:"))
        self.assertIsNone(parse_ack_custom_id("other:1"))

    def test_mark_as_read_components(self):
        components = mark_as_read_components(99)
        self.assertEqual(len(components), 1)
        button = components[0]["components"][0]
        self.assertEqual(button["label"], "Mark as read")
        self.assertEqual(button["custom_id"], "notif_ack:99")
        self.assertEqual(button["style"], 2)


class AckDeliveryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ackuser", password="x")
        self.other = User.objects.create_user("other", password="x")
        DiscordUser.objects.create(
            id=111222333,
            discord_tag="ackuser#0001",
            user=self.user,
        )
        DiscordUser.objects.create(
            id=444555666,
            discord_tag="other#0001",
            user=self.other,
        )
        self.delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.created",
            channel=NotificationChannel.DISCORD,
            payload={"body": "hi"},
            status=NotificationDeliveryStatus.SENT,
            discord_channel_id="999",
            discord_message_id="888",
        )

    def test_ack_marks_read(self):
        result = ack_delivery_for_discord_user(self.delivery.id, 111222333)
        self.assertEqual(result.status, NotificationDeliveryStatus.READ)
        self.assertIsNotNone(result.read_at)

    def test_ack_idempotent(self):
        first = ack_delivery_for_discord_user(self.delivery.id, 111222333)
        second = ack_delivery_for_discord_user(self.delivery.id, 111222333)
        self.assertEqual(first.read_at, second.read_at)

    def test_ack_wrong_user(self):
        with self.assertRaises(AckError) as ctx:
            ack_delivery_for_discord_user(self.delivery.id, 444555666)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_ack_unknown_delivery(self):
        with self.assertRaises(AckError) as ctx:
            ack_delivery_for_discord_user(999999, 111222333)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_ack_failed_status(self):
        self.delivery.status = NotificationDeliveryStatus.FAILED
        self.delivery.save(update_fields=["status"])
        with self.assertRaises(AckError) as ctx:
            ack_delivery_for_discord_user(self.delivery.id, 111222333)
        self.assertEqual(ctx.exception.status_code, 400)
