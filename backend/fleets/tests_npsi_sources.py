"""NPSI event sources managed from the site."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from fleets.helpers.npsi_ingest import feed_error_kind, poll_npsi_source
from fleets.models import (
    EveFleetAudience,
    NpsiEventSource,
    NpsiExternalEvent,
)

BASE = "/api/fleets/npsi-sources"


class SourceFixture:
    """A source and request helpers, shared by the source test cases."""

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


class NpsiSourceApiTestCase(SourceFixture, TestCase):
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
            ("post", f"/{self.source.id}/try", None),
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
        private = self.send(
            "post",
            "",
            {
                "name": "Loop",
                "feed_url": "http://10.1.2.3/feed.json",
                "fc_character_name": "FC",
            },
        )
        self.assertEqual(400, private.status_code)
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

    def test_a_private_feed_is_not_fetched(self):
        self.source.feed_url = "http://169.254.169.254/latest"
        self.source.save(update_fields=["feed_url"])
        with patch("fleets.helpers.npsi_ingest.requests.get") as mock_get:
            poll_npsi_source(self.source)
        mock_get.assert_not_called()
        self.source.refresh_from_db()
        self.assertIn("public address", self.source.last_error)

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


class NpsiSourceStatusTestCase(SourceFixture, TestCase):
    """The fields the manage screen draws a source's row from."""

    def test_list_classifies_the_error_and_counts_upcoming(self):
        self.grant()
        NpsiEventSource.objects.filter(pk=self.source.pk).update(
            last_error=(
                "Feed request failed: HTTPSConnectionPool(host='x', port=443):"
                " Read timed out. (read timeout=15)"
            ),
        )
        now = timezone.now()
        for hours, summary in ((-2, "past"), (3, "soon"), (30, "later")):
            NpsiExternalEvent.objects.create(
                source=self.source,
                fingerprint=summary,
                summary=summary,
                character_name="Some FC",
                start_time=now + timedelta(hours=hours),
            )
        data = self.send("get", "").json()
        row = data["sources"][0]
        self.assertEqual("timeout", row["last_error_kind"])
        self.assertEqual(3, row["event_count"])
        self.assertEqual(2, row["upcoming_count"])
        self.assertIsNone(row["fc_character_id"])
        self.assertEqual(15, data["feed_timeout_seconds"])

    def test_error_kinds(self):
        for error, kind in (
            ("", ""),
            ("Feed request failed: Read timed out.", "timeout"),
            ("Feed request failed: 404 Client Error: Not Found", "http"),
            (
                "Feed request failed: Feed URL is not a public address.",
                "not_public",
            ),
            ("The feed did not return a list of events.", "not_list"),
            (
                "Feed request failed: Expecting value: line 1 column 1",
                "not_json",
            ),
            (
                "Feed request failed: Max retries exceeded with url",
                "unreachable",
            ),
            ("Feed request failed: boom", "other"),
        ):
            with self.subTest(error=error):
                self.assertEqual(kind, feed_error_kind(error))


class NpsiSourceTryTestCase(SourceFixture, TestCase):
    """Try the feed now: a dry run that stores and sends nothing."""

    def feed(self, payload):
        response = MagicMock()
        response.is_redirect = False
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    def test_try_reads_the_feed_without_storing_or_posting(self):
        self.grant()
        soon = (timezone.now() + timedelta(hours=5)).isoformat()
        past = (timezone.now() - timedelta(hours=5)).isoformat()
        payload = [
            {"summary": "Roam", "start": soon, "character_name": "FC One"},
            {"summary": "Old", "start": past},
            {"summary": "No start"},
        ]
        with patch(
            "fleets.helpers.npsi_ingest.requests.get",
            return_value=self.feed(payload),
        ), patch("fleets.helpers.npsi_ingest.notify_fc") as notify:
            response = self.send("post", f"/{self.source.id}/try")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(3, data["item_count"])
        self.assertEqual(1, data["upcoming_count"])
        self.assertEqual("FC One", data["upcoming"][0]["character_name"])
        notify.assert_not_called()
        self.assertFalse(NpsiExternalEvent.objects.exists())
        self.source.refresh_from_db()
        self.assertIsNone(self.source.last_polled_at)

    def test_try_reports_a_timeout_in_plain_kind(self):
        self.grant()
        with patch(
            "fleets.helpers.npsi_ingest.requests.get",
            side_effect=requests.Timeout("Read timed out."),
        ):
            data = self.send("post", f"/{self.source.id}/try").json()
        self.assertFalse(data["ok"])
        self.assertEqual("timeout", data["error_kind"])
        self.assertEqual(15, data["feed_timeout_seconds"])
        self.source.refresh_from_db()
        self.assertEqual("", self.source.last_error)

    def test_try_unknown_source(self):
        self.grant()
        self.assertEqual(404, self.send("post", "/9999/try").status_code)
