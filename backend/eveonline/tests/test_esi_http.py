"""The shared raw ESI transport: identity, budget accounting, paging."""

from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from eveonline import esi_budget
from eveonline.client import ERROR_CALLING_ESI, SUCCESS, EsiClient
from eveonline.esi_http import MAX_PAGES, esi_request, user_agent
from eveonline.tests.fake_esi_http import FakeEsi, make_response


class EsiRequestTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeEsi().install(self)

    def test_sends_django_esi_user_agent_without_compat_by_default(self):
        self.fake.add(
            "GET", "/universe/schematics/65/", make_response(200, {})
        )
        esi_request("GET", "/universe/schematics/65/")
        headers = self.fake.calls[0]["headers"]
        self.assertEqual(headers["User-Agent"], user_agent())
        self.assertTrue(headers["User-Agent"].startswith("MinmatarOrg/1.0.0"))
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("X-Compatibility-Date", headers)

    def test_token_and_compat_headers(self):
        self.fake.add("GET", "/characters/1/fittings/", make_response(200, []))
        esi_request(
            "GET", "/characters/1/fittings/", access_token="t", compat=True
        )
        headers = self.fake.calls[0]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer t")
        self.assertEqual(headers["X-Compatibility-Date"], "2026-06-09")

    def test_full_url_is_used_as_is(self):
        self.fake.add("GET", "/killmails/1/abc/", make_response(200, {}))
        esi_request("GET", "https://esi.evetech.net/latest/killmails/1/abc/")
        self.assertEqual(self.fake.calls[0]["path"], "/killmails/1/abc/")

    def test_follows_x_pages(self):
        for page in ("1", "2", "3"):
            self.fake.add(
                "GET",
                "/x/",
                make_response(200, [int(page)], {"x-pages": "3"}),
                page=page,
            )
        result = esi_request("GET", "/x/", paged=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.data, [1, 2, 3])
        self.assertEqual(result.pages, 3)
        self.assertEqual(
            [c["query"]["page"] for c in self.fake.calls], ["1", "2", "3"]
        )

    def test_page_count_is_capped(self):
        self.fake.add(
            "GET", "/x/", make_response(200, [0], {"X-Pages": "100000"})
        )
        result = esi_request("GET", "/x/", paged=True)
        self.assertEqual(len(self.fake.calls), MAX_PAGES)
        self.assertEqual(result.pages, MAX_PAGES)

    def test_error_body_and_text_are_kept(self):
        self.fake.add("GET", "/x/", make_response(404, {"error": "gone"}))
        result = esi_request("GET", "/x/")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 404)
        self.assertEqual(result.data, {"error": "gone"})
        self.assertEqual(result.text, '{"error": "gone"}')

    def test_undecodable_success_is_an_error(self):
        self.fake.add("GET", "/x/", make_response(200, raw_text="<html>"))
        result = esi_request("GET", "/x/")
        self.assertFalse(result.ok)
        self.assertIsInstance(result.error, ValueError)

    def test_exception_is_returned_and_counted(self):
        self.fake.add("GET", "/x/", requests.Timeout("slow"))
        before = esi_budget.error_budget()
        result = esi_request("GET", "/x/")
        self.assertIsNone(result.status)
        self.assertIsInstance(result.error, requests.Timeout)
        self.assertEqual(esi_budget.error_budget(), before - 1)


class EsiRequestBudgetTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeEsi().install(self)

    def test_error_without_header_spends_error_budget(self):
        self.fake.add("GET", "/x/", make_response(500, None))
        before = esi_budget.error_budget()
        esi_request("GET", "/x/")
        self.assertEqual(esi_budget.error_budget(), before - 1)

    def test_remain_header_is_believed(self):
        self.fake.add(
            "GET",
            "/x/",
            make_response(
                403,
                None,
                {
                    "X-Esi-Error-Limit-Remain": "42",
                    "X-Esi-Error-Limit-Reset": "30",
                },
            ),
        )
        esi_request("GET", "/x/")
        self.assertEqual(esi_budget.error_budget(), 42)

    def test_420_pauses_every_group(self):
        self.fake.add(
            "GET",
            "/x/",
            make_response(420, None, {"X-Esi-Error-Limit-Reset": "45"}),
        )
        esi_request("GET", "/x/")
        self.assertGreater(esi_budget.pause_remaining("char-killmail", 1), 0)
        self.assertFalse(esi_budget.can_spend("killmail"))

    def test_success_does_not_touch_budget(self):
        self.fake.add("GET", "/x/", make_response(200, []))
        esi_request("GET", "/x/")
        self.assertEqual(esi_budget.error_budget(), 100)

    def test_account_false_leaves_accounting_to_caller(self):
        self.fake.add("GET", "/x/", make_response(500, None))
        with patch.object(esi_budget, "observe_response") as observe:
            esi_request("GET", "/x/", account=False)
        observe.assert_not_called()

    def test_client_raw_methods_are_accounted(self):
        self.fake.add("GET", "/characters/7/clones/", make_response(503, None))
        token = MagicMock()
        token.valid_access_token.return_value = "tok"
        with patch.object(
            EsiClient, "_valid_token", return_value=(token, SUCCESS)
        ):
            response = EsiClient(7).get_character_clones()
        self.assertEqual(response.response_code, 503)
        self.assertEqual(esi_budget.error_budget(), 99)
        self.assertEqual(
            self.fake.calls[0]["headers"]["User-Agent"], user_agent()
        )


class RawMethodExceptionTest(SimpleTestCase):
    """Methods that used to let a network error escape now return 906."""

    def setUp(self):
        cache.clear()
        self.fake = FakeEsi().install(self)

    def test_planets_network_error_is_error_calling_esi(self):
        self.fake.add(
            "GET", "/characters/7/planets/", requests.ConnectionError("x")
        )
        token = MagicMock()
        token.valid_access_token.return_value = "tok"
        with patch.object(
            EsiClient, "_valid_token", return_value=(token, SUCCESS)
        ):
            response = EsiClient(7).get_character_planets()
        self.assertEqual(response.response_code, ERROR_CALLING_ESI)
        self.assertFalse(response.success())
