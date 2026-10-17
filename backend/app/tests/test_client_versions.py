from datetime import date
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from app import client_versions


class ClientVersionTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_parse_accepts_desktop_versions_only(self):
        parse = client_versions.parse_client
        self.assertEqual(
            parse("desktop/0.10.0 (portable)"), "desktop/0.10.0 (portable)"
        )
        self.assertEqual(parse("desktop/1.2.3"), "desktop/1.2.3 (unknown)")
        junk_values = (
            None,
            "",
            "desktop/x",
            "web/1.0.0",
            "desktop/1.0.0 (" + "a" * 50 + ")",
        )
        for junk in junk_values:
            self.assertIsNone(parse(junk), junk)

    def test_counts_requests_per_version_per_day(self):
        client = Client()
        for _ in range(3):
            client.get(
                "/api/campaigns/overlay",
                HTTP_X_MINMATAR_CLIENT="desktop/0.10.0 (installer)",
            )
        client.get(
            "/api/campaigns/overlay",
            HTTP_X_MINMATAR_CLIENT="desktop/0.9.1 (portable)",
        )
        client.get("/api/campaigns/overlay")  # a browser or script
        today = client_versions.counts(1)
        self.assertEqual(
            list(today.values())[0],
            {
                "desktop/0.10.0 (installer)": 3,
                "desktop/0.9.1 (portable)": 1,
            },
        )
        out = StringIO()
        call_command("api_clients", "--days", "1", stdout=out)
        self.assertIn("desktop/0.10.0 (installer): 3", out.getvalue())

    def test_a_request_without_the_header_is_untouched(self):
        with mock.patch.object(client_versions, "record") as record:
            response = Client().get("/api/campaigns/overlay")
        record.assert_not_called()
        self.assertEqual(response.status_code, 401)

    def test_a_broken_cache_never_fails_the_request(self):
        with mock.patch.object(
            client_versions, "record", side_effect=RuntimeError("redis down")
        ):
            response = Client().get(
                "/api/campaigns/overlay",
                HTTP_X_MINMATAR_CLIENT="desktop/0.10.0 (installer)",
            )
        self.assertEqual(response.status_code, 401)

    def test_days_are_kept_apart(self):
        client_versions.record("desktop/0.1.0 (installer)", date(2026, 1, 1))
        client_versions.record("desktop/0.1.0 (installer)", date(2026, 1, 2))
        client_versions.record("desktop/0.1.0 (installer)", date(2026, 1, 2))
        self.assertEqual(
            client_versions.counts(2, today=date(2026, 1, 2)),
            {
                "2026-01-02": {"desktop/0.1.0 (installer)": 2},
                "2026-01-01": {"desktop/0.1.0 (installer)": 1},
            },
        )

    @override_settings(CORS_ALLOWED_ORIGINS=["https://web.example"])
    def test_browsers_are_not_invited_to_send_it(self):
        response = Client().options(
            "/api/campaigns/overlay", HTTP_ORIGIN="https://web.example"
        )
        self.assertNotIn(
            "x-minmatar-client",
            response["Access-Control-Allow-Headers"].lower(),
        )
