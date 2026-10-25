from datetime import timedelta
from unittest.mock import patch

from celery.exceptions import Retry
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.channels import (
    DISCORD_DM_LOCAL_BUCKET,
    ChannelSendError,
    ChannelSkip,
)
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
    NotificationTopicSubscription,
)
from notifications.rate_limit import paced_spacing
from notifications.registry import get_type
from notifications.service import (
    effective_preferences,
    notify_user,
    notify_users,
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
        closed = get_type("fleets.closed")
        self.assertTrue(closed.default_enabled(NotificationChannel.EVE_MAIL))


class PreferenceResolutionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("prefuser", password="x")

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
        # Web stays off until VAPID is configured. Discord is on; eve mail is off.
        self.assertEqual(channels, {NotificationChannel.DISCORD})
        self.assertEqual(mock_delay.call_count, 1)

    @override_settings(VAPID_PRIVATE_KEY="test-key")
    @patch("notifications.service.deliver_notification.delay")
    def test_notify_includes_web_when_vapid_is_set(self, mock_delay):
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
        spacing = paced_spacing(2.0, 2.0)
        self.assertEqual(countdowns, [spacing, spacing * 2])

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
    def test_local_bucket_retries_past_failure_budget(self, mock_send):
        mock_send.side_effect = ChannelSendError(
            DISCORD_DM_LOCAL_BUCKET,
            retryable=True,
            retry_after=2.5,
        )
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        request = deliver_notification.request
        previous = request.retries
        request.retries = deliver_notification.max_retries
        captured = {}

        def stop_retry(**kwargs):
            captured.update(kwargs)
            raise Retry()

        try:
            with patch.object(deliver_notification, "retry", stop_retry):
                with self.assertRaises(Retry):
                    deliver_notification(delivery.id)
        finally:
            request.retries = previous
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.PENDING)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(
            captured["max_retries"], deliver_notification.max_retries + 1
        )
        self.assertEqual(captured["countdown"], 2)

    @patch("notifications.tasks.send_channel")
    def test_local_bucket_denials_still_send(self, mock_send):
        calls = {"n": 0}

        def send(*args, **kwargs):
            del args, kwargs
            calls["n"] += 1
            if calls["n"] <= deliver_notification.max_retries:
                raise ChannelSendError(
                    DISCORD_DM_LOCAL_BUCKET,
                    retryable=True,
                    retry_after=1.0,
                )
            return {"discord_channel_id": "1", "discord_message_id": "2"}

        mock_send.side_effect = send
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        request = deliver_notification.request
        previous = request.retries

        def stop_retry(**kwargs):
            del kwargs
            raise Retry()

        try:
            with patch.object(deliver_notification, "retry", stop_retry):
                result = None
                for attempt in range(deliver_notification.max_retries + 2):
                    request.retries = attempt
                    try:
                        result = deliver_notification(delivery.id)
                        break
                    except Retry:
                        continue
        finally:
            request.retries = previous
        self.assertEqual(result, "sent")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.SENT)
        self.assertGreater(delivery.attempts, deliver_notification.max_retries)

    @patch("notifications.tasks.send_channel")
    def test_local_bucket_fails_after_deadline(self, mock_send):
        mock_send.side_effect = ChannelSendError(
            DISCORD_DM_LOCAL_BUCKET,
            retryable=True,
            retry_after=1.0,
        )
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            created_at=timezone.now() - timedelta(minutes=16)
        )
        result = deliver_notification(delivery.id)
        self.assertEqual(result, "failed")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.FAILED)

    @patch("notifications.tasks.send_channel")
    def test_other_errors_stop_at_max_retries(self, mock_send):
        mock_send.side_effect = ChannelSendError(
            "Discord API rate limited",
            retryable=True,
            retry_after=5.0,
        )
        delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.assignment",
            channel=NotificationChannel.DISCORD,
            payload={"discord_message": "hi"},
        )
        request = deliver_notification.request
        previous = request.retries
        request.retries = deliver_notification.max_retries
        try:
            with patch.object(
                deliver_notification, "retry", side_effect=Retry()
            ):
                result = deliver_notification(delivery.id)
        finally:
            request.retries = previous
        self.assertEqual(result, "failed")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.FAILED)

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
