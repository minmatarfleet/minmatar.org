"""NPSI event sources managed from the site."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from fleets.helpers.npsi_ingest import poll_npsi_source
from fleets.models import (
    EveFleetAudience,
    NpsiEventSource,
    NpsiExternalEvent,
)

BASE = "/api/fleets/npsi-sources"


class NpsiSourceApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.source = NpsiEventSource.objects.create(
            name="Test Feed",
            feed_url="https://example.org/feed.json",
            fc_character_name="Some FC",
        )

    def grant(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="change_npsieventsource",
                content_type__app_label="fleets",
            )
        )

    def send(self, method, path, data=None):
        return getattr(self.client, method)(
            BASE + path,
            data=json.dumps(data) if data is not None else None,
            content_type="application/json",
            **self.headers,
        )

    def test_everything_needs_the_feature(self):
        body = {
            "name": "x",
            "feed_url": "https://x.org",
            "fc_character_name": "x",
        }
        for method, path, data in (
            ("get", "", None),
            ("post", "", body),
            ("patch", f"/{self.source.id}", {"enabled": False}),
            ("get", f"/{self.source.id}/events", None),
        ):
            with self.subTest(method=method, path=path):
                response = self.send(method, path, data)
                self.assertEqual(403, response.status_code)

    def test_list_shows_status_and_audiences(self):
        self.grant()
        audience = EveFleetAudience.objects.create(name="Alliance")
        NpsiEventSource.objects.filter(pk=self.source.pk).update(
            last_error="Feed request failed: boom",
            default_audience=audience,
        )
        data = self.send("get", "").json()
        self.assertEqual(
            "Feed request failed: boom", data["sources"][0]["last_error"]
        )
        self.assertEqual(
            "Alliance", data["sources"][0]["default_audience_name"]
        )
        self.assertEqual(["Alliance"], [a["name"] for a in data["audiences"]])

    def test_create_validates_and_adds(self):
        self.grant()
        bad = self.send(
            "post",
            "",
            {"name": "X", "feed_url": "not a url", "fc_character_name": "FC"},
        )
        self.assertEqual(400, bad.status_code)
        duplicate = self.send(
            "post",
            "",
            {
                "name": "Test Feed",
                "feed_url": "https://example.org/b.json",
                "fc_character_name": "FC",
            },
        )
        self.assertEqual(400, duplicate.status_code)
        ok = self.send(
            "post",
            "",
            {
                "name": "Other",
                "feed_url": "https://example.org/b.json",
                "fc_character_name": "FC",
            },
        )
        self.assertEqual(200, ok.status_code)
        self.assertTrue(NpsiEventSource.objects.filter(name="Other").exists())

    def test_disable_and_edit(self):
        self.grant()
        response = self.send(
            "patch",
            f"/{self.source.id}",
            {"enabled": False, "fc_character_name": "New FC"},
        )
        self.assertEqual(200, response.status_code)
        self.source.refresh_from_db()
        self.assertFalse(self.source.enabled)
        self.assertEqual("New FC", self.source.fc_character_name)
        blank = self.send("patch", f"/{self.source.id}", {"name": " "})
        self.assertEqual(400, blank.status_code)
        missing = self.send("patch", "/999", {"enabled": True})
        self.assertEqual(404, missing.status_code)

    def test_preview_lists_only_upcoming_events(self):
        self.grant()
        now = timezone.now()
        for index, offset in enumerate((-2, 3)):
            NpsiExternalEvent.objects.create(
                source=self.source,
                fingerprint=f"fp{index}",
                summary=f"Event {index}",
                start_time=now + timedelta(days=offset),
            )
        events = self.send("get", f"/{self.source.id}/events").json()
        self.assertEqual(["Event 1"], [e["summary"] for e in events])


class NpsiPollStatusTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.source = NpsiEventSource.objects.create(
            name="Test Feed",
            feed_url="https://example.org/feed.json",
            fc_character_name="Some FC",
        )

    def test_a_good_poll_records_success(self):
        response = MagicMock()
        response.json.return_value = []
        with patch(
            "fleets.helpers.npsi_ingest.requests.get", return_value=response
        ):
            poll_npsi_source(self.source)
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.last_success_at)
        self.assertEqual("", self.source.last_error)

    def test_a_failed_poll_records_the_error(self):
        with patch(
            "fleets.helpers.npsi_ingest.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            poll_npsi_source(self.source)
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.last_polled_at)
        self.assertIsNone(self.source.last_success_at)
        self.assertIn("boom", self.source.last_error)
