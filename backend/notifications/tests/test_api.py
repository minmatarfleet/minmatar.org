import json

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase

from discord.models import DiscordUser
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
    NotificationTopicSubscription,
)

BASE = "/api/notifications"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class PreferencesApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("apiuser", password="x")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_make_token(self.user)}"}

    def test_get_preferences(self):
        response = self.client.get(f"{BASE}/preferences", **self.auth)
        self.assertEqual(response.status_code, 200)
        features = response.json()
        self.assertTrue(any(f["feature"] == "industry" for f in features))
        industry = next(f for f in features if f["feature"] == "industry")
        keys = {t["key"] for t in industry["types"]}
        self.assertIn("industry.order.created", keys)

    def test_put_preferences(self):
        response = self.client.put(
            f"{BASE}/preferences",
            data=json.dumps(
                {
                    "preferences": [
                        {
                            "notification_type": "industry.order.created",
                            "channel": NotificationChannel.DISCORD,
                            "enabled": True,
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        pref = NotificationPreference.objects.get(
            user=self.user,
            notification_type="industry.order.created",
            channel=NotificationChannel.DISCORD,
        )
        self.assertTrue(pref.enabled)

    def test_put_rejects_unknown_type(self):
        response = self.client.put(
            f"{BASE}/preferences",
            data=json.dumps(
                {
                    "preferences": [
                        {
                            "notification_type": "nope.missing",
                            "channel": "web",
                            "enabled": True,
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    def test_topic_subscribe_unsubscribe(self):
        response = self.client.post(
            f"{BASE}/topics/industry.order.created", **self.auth
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            NotificationTopicSubscription.objects.filter(
                user=self.user, notification_type="industry.order.created"
            ).exists()
        )
        response = self.client.delete(
            f"{BASE}/topics/industry.order.created", **self.auth
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            NotificationTopicSubscription.objects.filter(
                user=self.user, notification_type="industry.order.created"
            ).exists()
        )

    def test_topic_rejects_non_broadcast(self):
        response = self.client.post(
            f"{BASE}/topics/industry.order.assignment", **self.auth
        )
        self.assertEqual(response.status_code, 400)


class AckDeliveryApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("ackapi", password="x")
        self.bot = User.objects.create_user("bot", password="x", is_staff=True)
        DiscordUser.objects.create(
            id=777888999,
            discord_tag="ackapi#0001",
            user=self.user,
        )
        self.delivery = NotificationDelivery.objects.create(
            user=self.user,
            notification_type="industry.order.created",
            channel=NotificationChannel.DISCORD,
            payload={"body": "hi"},
            status=NotificationDeliveryStatus.SENT,
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_make_token(self.bot)}"}

    def test_ack_success(self):
        response = self.client.post(
            f"{BASE}/deliveries/{self.delivery.id}/ack",
            data=json.dumps({"discord_user_id": 777888999}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "read")
        self.assertTrue(body["delete_message"])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, NotificationDeliveryStatus.READ)

    def test_ack_forbidden_for_other_discord_user(self):
        DiscordUser.objects.create(
            id=111,
            discord_tag="stranger#0001",
            user=User.objects.create_user("stranger", password="x"),
        )
        response = self.client.post(
            f"{BASE}/deliveries/{self.delivery.id}/ack",
            data=json.dumps({"discord_user_id": 111}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)

    def test_ack_forbidden_for_non_staff_with_victim_discord_id(self):
        stranger = User.objects.create_user("nosy", password="x")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {_make_token(stranger)}"}
        response = self.client.post(
            f"{BASE}/deliveries/{self.delivery.id}/ack",
            data=json.dumps({"discord_user_id": 777888999}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(response.status_code, 403)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, NotificationDeliveryStatus.SENT)

    def test_ack_owner_can_ack_own_delivery(self):
        auth = {"HTTP_AUTHORIZATION": f"Bearer {_make_token(self.user)}"}
        response = self.client.post(
            f"{BASE}/deliveries/{self.delivery.id}/ack",
            data=json.dumps({"discord_user_id": 777888999}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(response.status_code, 200)
