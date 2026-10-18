from __future__ import annotations

from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from eveonline.esi_http import user_agent
from eveonline.tests.fake_esi_http import FakeEsi, make_response
from feed.constants import R2Z2_BASE_URL, R2Z2_USER_AGENT
from feed.helpers import zkill_client

PATH = "/killmails/1/abc/"


class ZkillClientTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeEsi().install(self)

    def test_headers_identify_the_feed(self):
        self.assertEqual(
            zkill_client.headers(),
            {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"},
        )

    def test_r2z2_url_uses_the_one_base(self):
        self.assertEqual(
            zkill_client.r2z2_sequence_url(5), f"{R2Z2_BASE_URL}/5.json"
        )

    @patch("feed.helpers.zkill_client.requests.get")
    def test_zkill_get_sends_headers(self, get):
        zkill_client.zkill_get(
            "https://zkillboard.com/api/x/", params={"a": 1}
        )
        get.assert_called_once_with(
            "https://zkillboard.com/api/x/",
            headers=zkill_client.headers(),
            params={"a": 1},
            timeout=60,
        )

    def test_killmail_fetch_uses_the_esi_transport(self):
        self.fake.add("GET", PATH, make_response(200, {"killmail_id": 1}))
        self.assertEqual(
            zkill_client.fetch_esi_killmail(1, "abc"), {"killmail_id": 1}
        )
        self.assertEqual(
            self.fake.calls[0]["headers"]["User-Agent"], user_agent()
        )

    @patch("feed.helpers.zkill_client.time.sleep")
    def test_429_is_retried(self, sleep):
        responses = iter(
            [make_response(429, None), make_response(200, {"ok": True})]
        )
        original = self.fake.handle

        def handle(prepared):
            self.fake.routes[("GET", PATH, None)] = next(responses)
            return original(prepared)

        self.fake.handle = handle
        self.assertEqual(
            zkill_client.fetch_esi_killmail(1, "abc"), {"ok": True}
        )
        sleep.assert_called_once_with(1)
        self.assertEqual(len(self.fake.calls), 2)

    @patch("feed.helpers.zkill_client.time.sleep")
    def test_429_on_last_attempt_raises(self, sleep):
        del sleep
        self.fake.add("GET", PATH, make_response(429, None))
        with self.assertRaises(requests.HTTPError):
            zkill_client.fetch_esi_killmail(1, "abc")
        self.assertEqual(len(self.fake.calls), 3)

    def test_404_and_420_are_none(self):
        for status in (404, 420):
            self.fake.add("GET", PATH, make_response(status, None))
            self.assertIsNone(zkill_client.fetch_esi_killmail(1, "abc"))

    def test_server_error_raises(self):
        self.fake.add("GET", PATH, make_response(502, None))
        with self.assertRaises(requests.HTTPError):
            zkill_client.fetch_esi_killmail(1, "abc")

    def test_network_error_raises(self):
        self.fake.add("GET", PATH, requests.ConnectionError("down"))
        with self.assertRaises(requests.ConnectionError):
            zkill_client.fetch_esi_killmail(1, "abc")
