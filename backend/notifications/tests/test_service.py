from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from notifications.channels import ChannelSkip
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
    NotificationTopicSubscription,
)
from notifications.registry import get_type
from notifications.service import (
    effective_preferences,
    notify_user,
    notify_users,
    preference_enabled,
)
from notifications.tasks import deliver_notification


class RegistryTestCase(TestCase):
    def test_industry_types_registered(self):
        created = get_type("industry.order.created")
        self.assertTrue(created.supports_topic_subscription)
        self.assertIn(NotificationChannel.WEB, created.allowed_channels())
        assignment = get_type("industry.order.assignment")
        self.assertFalse(assignment.supports_topic_subscription)
        get_type("industry.order.job")


class PreferenceResolutionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("prefuser", password="x")

    def test_defaults_when_no_row(self):
        ntype = get_type("industry.order.created")
        self.assertTrue(
            preference_enabled(self.user, ntype, NotificationChannel.WEB)
        )
        self.assertFalse(
            preference_enabled(self.user, ntype, NotificationChannel.DISCORD)
        )

    def test_explicit_override(self):
        NotificationPreference.objects.create(
            user=self.user,
            notification_type="industry.order.created",
            channel=NotificationChannel.DISCORD,
            enabled=True,
        )
        ntype = get_type("industry.order.created")
        self.assertTrue(
            preference_enabled(self.user, ntype, NotificationChannel.DISCORD)
        )

    def test_effective_preferences_shape(self):
        prefs = effective_preferences(self.user)
        self.assertIn("industry.order.created", prefs)
        self.assertIn(NotificationChannel.WEB, prefs["industry.order.created"])


class NotifyServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("notifyuser", password="x")

    @patch("notifications.service.deliver_notification.delay")
    def test_notify_respects_channel_defaults(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            deliveries = notify_user(
                self.user,
                "industry.order.assignment",
                {
                    "order_id": 1,
                    "public_short_code": "ABC",
                    "item_id": 2,
                    "assignment_id": 3,
                    "item_name": "Rifter",
                    "quantity": 1,
                    "coordinators": [],
                },
            )
        channels = {d.channel for d in deliveries}
        # defaults: web + discord on, eve_mail off
        self.assertEqual(
            channels,
            {NotificationChannel.WEB, NotificationChannel.DISCORD},
        )
        self.assertEqual(mock_delay.call_count, 2)

    @patch("notifications.service.deliver_notification.apply_async")
    @patch("notifications.service.deliver_notification.delay")
    def test_stagger_paces_discord_enqueue(self, mock_delay, mock_async):
        users = [
            User.objects.create_user(f"stag{i}", password="x")
            for i in range(3)
        ]
        for user in users:
            NotificationPreference.objects.create(
                user=user,
                notification_type="industry.order.created",
                channel=NotificationChannel.DISCORD,
                enabled=True,
            )
            NotificationPreference.objects.create(
                user=user,
                notification_type="industry.order.created",
                channel=NotificationChannel.WEB,
                enabled=False,
            )
        with self.captureOnCommitCallbacks(execute=True):
            notify_users(
                users,
                "industry.order.created",
                {
                    "order_id": 1,
                    "public_short_code": "ABC",
                    "items": ["1× Rifter"],
                },
                stagger_rate_limited_channels=True,
            )
        self.assertEqual(mock_delay.call_count, 1)
        self.assertEqual(mock_async.call_count, 2)
        countdowns = sorted(
            call.kwargs.get("countdown", 0)
            for call in mock_async.call_args_list
        )
        self.assertGreater(countdowns[0], 0)
        self.assertGreater(countdowns[1], countdowns[0])

    @patch("notifications.service.deliver_notification.delay")
    def test_idempotency_skips_duplicate(self, mock_delay):
        ctx = {
            "order_id": 1,
            "public_short_code": "ABC",
            "item_id": 2,
            "assignment_id": 3,
            "item_name": "Rifter",
            "quantity": 1,
            "coordinators": [],
        }
        with self.captureOnCommitCallbacks(execute=True):
            first = notify_user(
                self.user,
                "industry.order.assignment",
                ctx,
                idempotency_key="test-key-1",
            )
            second = notify_user(
                self.user,
                "industry.order.assignment",
                ctx,
                idempotency_key="test-key-1",
            )
        self.assertTrue(first)
        self.assertEqual(second, [])
        self.assertEqual(
            NotificationDelivery.objects.filter(
                user=self.user, notification_type="industry.order.assignment"
            ).count(),
            len(first),
        )


class TopicSubscriptionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("topicuser", password="x")

    def test_topic_subscribe(self):
        NotificationTopicSubscription.objects.create(
            user=self.user, notification_type="industry.order.created"
        )
        self.assertTrue(
            NotificationTopicSubscription.objects.filter(
                user=self.user, notification_type="industry.order.created"
            ).exists()
        )


class DeliveryTaskTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("delivuser", password="x")

    @patch("notifications.tasks.send_channel")
    def test_deliver_marks_sent(self, mock_send):
        mock_send.return_value = {
            "discord_channel_id": "123",
            "discord_message_id": "456",
        }
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        result = deliver_notification(delivery.id)
        self.assertEqual(result, "sent")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.SENT)
        self.assertEqual(delivery.discord_channel_id, "123")
        self.assertEqual(delivery.discord_message_id, "456")
        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args.kwargs.get("delivery_id"), delivery.id
        )

    @patch("notifications.tasks.send_channel")
    def test_deliver_skips(self, mock_send):
        mock_send.side_effect = ChannelSkip("No Discord link")
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        result = deliver_notification(delivery.id)
        self.assertEqual(result, "skipped")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.SKIPPED)

    @patch("notifications.tasks.send_channel")
    def test_deliver_does_not_overwrite_read(self, mock_send):
        mock_send.return_value = {
            "discord_channel_id": "123",
            "discord_message_id": "456",
        }
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
            status=NotificationDeliveryStatus.PENDING,
        )

        def mark_read_during_send(*args, **kwargs):
            NotificationDelivery.objects.filter(pk=delivery.pk).update(
                status=NotificationDeliveryStatus.READ,
            )
            return {
                "discord_channel_id": "123",
                "discord_message_id": "456",
            }

        mock_send.side_effect = mark_read_during_send
        result = deliver_notification(delivery.id)
        self.assertEqual(result, "sent_already_read")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.READ)
        self.assertEqual(delivery.discord_message_id, "456")
