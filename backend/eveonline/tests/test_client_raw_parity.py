"""Recorded-response parity tests for EsiClient's raw ESI routes.

These run the same fixtures through each method and pin the requests made
and the ``EsiResponse`` returned, so moving the methods onto the shared
transport is checked against the hand-written loops they replace.
"""

from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from eveonline.client import (
    ERROR_CALLING_ESI,
    SUCCESS,
    EsiClient,
    get_region_market_orders_pages,
)
from eveonline.tests.fake_esi_http import FakeEsi, make_response

CHAR = 634915984
CORP = 98000001


def _token():
    token = MagicMock()
    token.valid_access_token.return_value = "tok"
    token.character_id = CHAR
    return token


class _Base(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch.object(
            EsiClient, "_valid_token", return_value=(_token(), SUCCESS)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fake = FakeEsi().install(self)

    def paged(self, path, pages, extra_query=None):
        """Register ``pages`` (a list of row lists) with X-Pages."""
        for number, rows in enumerate(pages, start=1):
            self.fake.add(
                "GET",
                path,
                make_response(200, rows, {"X-Pages": str(len(pages))}),
                page=str(number),
            )
        query = tuple(sorted((extra_query or {}).items()))
        return [
            ("GET", path, tuple(sorted(query + (("page", str(n)),))))
            for n in range(1, len(pages) + 1)
        ]


class PagedRouteParityTest(_Base):
    """The six hand-copied X-Pages loops."""

    def check_paged(self, call, path, extra_query=None):
        expected = self.paged(
            path, [[{"n": 1}], [{"n": 2}], [{"n": 3}]], extra_query
        )
        response = call()
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, [{"n": 1}, {"n": 2}, {"n": 3}])
        self.assertEqual(self.fake.requested(), expected)
        for c in self.fake.calls:
            self.assertEqual(c["headers"]["Authorization"], "Bearer tok")

    def test_character_blueprints(self):
        self.check_paged(
            EsiClient(CHAR).get_character_blueprints,
            f"/characters/{CHAR}/blueprints/",
        )

    def test_corporation_blueprints(self):
        self.check_paged(
            lambda: EsiClient(CHAR).get_corporation_blueprints(CORP),
            f"/corporations/{CORP}/blueprints/",
        )

    def test_corporation_industry_jobs(self):
        self.check_paged(
            lambda: EsiClient(CHAR).get_corporation_industry_jobs(CORP),
            f"/corporations/{CORP}/industry/jobs/",
            {"include_completed": "True"},
        )

    def test_corporation_roles(self):
        self.check_paged(
            lambda: EsiClient(CHAR).get_corporation_roles(CORP),
            f"/corporations/{CORP}/roles/",
        )

    def test_corporation_titles(self):
        self.check_paged(
            lambda: EsiClient(CHAR).get_corporation_titles(CORP),
            f"/corporations/{CORP}/titles/",
        )

    def test_corporation_member_titles(self):
        self.check_paged(
            lambda: EsiClient(CHAR).get_corporation_member_titles(CORP),
            f"/corporations/{CORP}/members/titles/",
        )

    def test_first_page_error_returns_status(self):
        path = f"/corporations/{CORP}/roles/"
        self.fake.add("GET", path, make_response(403, {"error": "no"}))
        response = EsiClient(CHAR).get_corporation_roles(CORP)
        self.assertEqual(response.response_code, 403)
        self.assertIsNone(response.response)
        self.assertEqual(len(self.fake.calls), 1)

    def test_later_page_error_fails_whole_call(self):
        path = f"/corporations/{CORP}/blueprints/"
        self.fake.add(
            "GET", path, make_response(200, [1], {"X-Pages": "3"}), page="1"
        )
        self.fake.add("GET", path, make_response(502, None), page="2")
        response = EsiClient(CHAR).get_corporation_blueprints(CORP)
        self.assertEqual(response.response_code, 502)
        self.assertEqual(len(self.fake.calls), 2)

    def test_exception_maps_to_error_calling_esi(self):
        path = f"/characters/{CHAR}/blueprints/"
        boom = requests.ConnectionError("down")
        self.fake.add("GET", path, boom)
        response = EsiClient(CHAR).get_character_blueprints()
        self.assertEqual(response.response_code, ERROR_CALLING_ESI)
        self.assertIs(response.response, boom)

    def test_missing_x_pages_reads_one_page(self):
        path = f"/characters/{CHAR}/blueprints/"
        self.fake.add("GET", path, make_response(200, [{"a": 1}]))
        response = EsiClient(CHAR).get_character_blueprints()
        self.assertEqual(response.data, [{"a": 1}])
        self.assertEqual(len(self.fake.calls), 1)

    def test_empty_body_is_empty_list(self):
        path = f"/characters/{CHAR}/blueprints/"
        self.fake.add("GET", path, make_response(200, None))
        response = EsiClient(CHAR).get_character_blueprints()
        self.assertEqual(response.data, [])

    def test_wallet_journal_walks_each_division(self):
        expected = []
        for division in range(1, 8):
            path = f"/corporations/{CORP}/wallets/{division}/journal/"
            pages = [[{"id": division * 10 + 1}]]
            if division == 2:
                pages.append([{"id": 22}])
            expected += self.paged(path, pages)
        response = EsiClient(
            CHAR
        ).get_corporation_wallet_journal_all_divisions(CORP)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(self.fake.requested(), expected)
        self.assertEqual(
            [(e["id"], e["division"]) for e in response.data],
            [(11, 1), (21, 2), (22, 2)]
            + [(d * 10 + 1, d) for d in range(3, 8)],
        )


class SingleRouteParityTest(_Base):
    def test_corporation_wallets(self):
        path = f"/corporations/{CORP}/wallets/"
        self.fake.add("GET", path, make_response(200, [{"division": 1}]))
        response = EsiClient(CHAR).get_corporation_wallets(CORP)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, [{"division": 1}])
        self.assertEqual(self.fake.requested(), [("GET", path, ())])

    def test_corporation_wallet_transactions(self):
        for division in range(1, 8):
            self.fake.add(
                "GET",
                f"/corporations/{CORP}/wallets/{division}/transactions/",
                make_response(200, [{"t": division}]),
            )
        response = EsiClient(CHAR).get_corporation_wallet_transactions(CORP)
        self.assertEqual(
            response.data,
            [{"t": d, "division": d} for d in range(1, 8)],
        )
        self.assertEqual(len(self.fake.calls), 7)

    def test_wallet_transactions_error_stops(self):
        self.fake.add(
            "GET",
            f"/corporations/{CORP}/wallets/1/transactions/",
            make_response(403, {"error": "role"}),
        )
        response = EsiClient(CHAR).get_corporation_wallet_transactions(CORP)
        self.assertEqual(response.response_code, 403)
        self.assertEqual(len(self.fake.calls), 1)

    def test_region_market_history(self):
        path = "/markets/10000002/history/"
        self.fake.add("GET", path, make_response(200, [{"average": 1.5}]))
        response = EsiClient(None).get_region_market_history(10000002, 34)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, [{"average": 1.5}])
        self.assertEqual(
            self.fake.requested(), [("GET", path, (("type_id", "34"),))]
        )
        self.assertNotIn("Authorization", self.fake.calls[0]["headers"])

    def test_region_market_history_error(self):
        self.fake.add(
            "GET", "/markets/10000002/history/", make_response(404, None)
        )
        response = EsiClient(None).get_region_market_history(10000002, 34)
        self.assertEqual(response.response_code, 404)

    def test_active_fleet_success_and_error_body(self):
        path = f"/characters/{CHAR}/fleet/"
        self.fake.add("GET", path, make_response(200, {"fleet_id": 7}))
        response = EsiClient(CHAR).get_active_fleet()
        self.assertTrue(response.success())
        self.assertEqual(response.response_code, 200)
        self.assertEqual(response.data, {"fleet_id": 7})

        self.fake.add(
            "GET",
            path,
            make_response(404, {"error": "Character is not in a fleet"}),
        )
        response = EsiClient(CHAR).get_active_fleet()
        self.assertEqual(response.response_code, 404)
        self.assertEqual(
            response.data, {"error": "Character is not in a fleet"}
        )

    def _simple_200_or_status(self, call, path):
        self.fake.add("GET", path, make_response(200, [{"x": 1}]))
        response = call()
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, [{"x": 1}])
        self.fake.add("GET", path, make_response(403, {"error": "scope"}))
        response = call()
        self.assertEqual(response.response_code, 403)
        self.assertIsNone(response.data)

    def test_character_planets(self):
        self._simple_200_or_status(
            EsiClient(CHAR).get_character_planets,
            f"/characters/{CHAR}/planets/",
        )

    def test_character_planet_details(self):
        self._simple_200_or_status(
            lambda: EsiClient(CHAR).get_character_planet_details(40000001),
            f"/characters/{CHAR}/planets/40000001/",
        )

    def test_universe_schematic(self):
        self._simple_200_or_status(
            lambda: EsiClient(None).get_universe_schematic(65),
            "/universe/schematics/65/",
        )

    def test_character_clones(self):
        self._simple_200_or_status(
            EsiClient(CHAR).get_character_clones,
            f"/characters/{CHAR}/clones/",
        )

    def test_character_implants(self):
        self._simple_200_or_status(
            EsiClient(CHAR).get_character_implants,
            f"/characters/{CHAR}/implants/",
        )

    def test_mining_ledger_reads_every_page(self):
        """Was page 1 only; ESI pages the ledger at 1000 rows."""
        expected = self.paged(
            f"/characters/{CHAR}/mining/",
            [[{"quantity": 1}], [{"quantity": 2}]],
        )
        response = EsiClient(CHAR).get_character_mining_ledger()
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, [{"quantity": 1}, {"quantity": 2}])
        self.assertEqual(self.fake.requested(), expected)

    def test_mining_ledger_error(self):
        self.fake.add(
            "GET",
            f"/characters/{CHAR}/mining/",
            make_response(403, {"error": "scope"}),
        )
        response = EsiClient(CHAR).get_character_mining_ledger()
        self.assertEqual(response.response_code, 403)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    def test_search_category(self):
        path = f"/characters/{CHAR}/search/"
        self.fake.add("GET", path, make_response(200, {"corporation": [1]}))
        response = EsiClient(CHAR).search_category("corporation", "abc")
        self.assertEqual(response.response_code, 200)
        self.assertEqual(response.data, {"corporation": [1]})
        self.assertEqual(
            self.fake.requested(),
            [
                (
                    "GET",
                    path,
                    (
                        ("categories", "corporation"),
                        ("search", "abc"),
                        ("strict", "false"),
                    ),
                )
            ],
        )
        self.fake.add("GET", path, make_response(200, ["not", "a dict"]))
        response = EsiClient(CHAR).search_category("corporation", "abc")
        self.assertEqual(response.data, {})

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    def test_set_autopilot_waypoint(self):
        path = "/ui/autopilot/waypoint/"
        self.fake.add("POST", path, make_response(204, None))
        response = EsiClient(CHAR).set_autopilot_waypoint(30002537)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(
            self.fake.requested(),
            [
                (
                    "POST",
                    path,
                    (
                        ("add_to_beginning", "false"),
                        ("clear_other_waypoints", "true"),
                        ("destination_id", "30002537"),
                    ),
                )
            ],
        )
        self.fake.add("POST", path, make_response(403, None))
        response = EsiClient(CHAR).set_autopilot_waypoint(30002537, False)
        self.assertEqual(response.response_code, 403)

    def test_notifications_200_keeps_response(self):
        path = f"/characters/{CHAR}/notifications/"
        self.fake.add(
            "GET", path, make_response(200, [{"notification_id": 1}])
        )
        response = EsiClient(CHAR).get_character_notifications()
        self.assertEqual(response.response_code, 200)
        self.assertEqual(response.data, [{"notification_id": 1}])
        self.assertEqual(response.response.status_code, 200)

    def test_notifications_error_keeps_text(self):
        path = f"/characters/{CHAR}/notifications/"
        self.fake.add("GET", path, make_response(420, {"error": "limit"}))
        response = EsiClient(CHAR).get_character_notifications()
        self.assertEqual(response.response_code, 420)
        self.assertEqual(response.data, '{"error": "limit"}')


class CompatRouteParityTest(_Base):
    """Routes that already sent X-Compatibility-Date."""

    def test_create_fitting(self):
        path = f"/characters/{CHAR}/fittings/"
        self.fake.add("POST", path, make_response(201, {"fitting_id": 9}))
        response = EsiClient(CHAR).create_character_fitting({"name": "x"})
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.data, {"fitting_id": 9})
        call = self.fake.calls[0]
        self.assertEqual(call["headers"]["X-Compatibility-Date"], "2026-06-09")
        self.assertEqual(call["body"], b'{"name": "x"}')

    def test_delete_fitting_error_keeps_text(self):
        path = f"/characters/{CHAR}/fittings/5/"
        self.fake.add("DELETE", path, make_response(404, None))
        response = EsiClient(CHAR).delete_character_fitting(5)
        self.assertEqual(response.response_code, 404)
        self.assertEqual(response.response, "")

    def test_delete_fitting_no_content(self):
        path = f"/characters/{CHAR}/fittings/5/"
        self.fake.add("DELETE", path, make_response(204, None))
        response = EsiClient(CHAR).delete_character_fitting(5)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertIsNone(response.data)

    def test_project_cursor_walk(self):
        path = f"/corporations/{CORP}/projects"
        first = make_response(
            200, {"projects": [{"id": "a"}], "cursor": {"before": "c1"}}
        )
        second = make_response(
            200, {"projects": [{"id": "b"}], "cursor": {"before": "c2"}}
        )
        third = make_response(200, {"projects": [], "cursor": {}})
        responses = iter([first, second, third])

        # Same path each page, distinguished by the before cursor.
        original = self.fake.handle

        def handle(prepared):
            self.fake.routes[("GET", path, None)] = next(responses)
            return original(prepared)

        self.fake.handle = handle
        response = EsiClient(CHAR).get_corporation_projects(CORP)
        self.assertEqual(response.data, [{"id": "a"}, {"id": "b"}])
        self.assertEqual(
            [c["query"] for c in self.fake.calls],
            [
                {"state": "All", "limit": "100"},
                {"state": "All", "limit": "100", "before": "c1"},
                {"state": "All", "limit": "100", "before": "c2"},
            ],
        )
        for c in self.fake.calls:
            self.assertEqual(
                c["headers"]["X-Compatibility-Date"], "2026-06-09"
            )

    def test_project_detail(self):
        path = f"/corporations/{CORP}/projects/p1"
        self.fake.add("GET", path, make_response(200, {"id": "p1"}))
        response = EsiClient(CHAR).get_corporation_project(CORP, "p1")
        self.assertEqual(response.data, {"id": "p1"})


class RegionOrdersParityTest(_Base):
    def test_yields_each_page(self):
        path = "/markets/10000002/orders/"
        full = [{"order_id": i} for i in range(1000)]
        self.fake.add(
            "GET", path, make_response(200, full, {"X-Pages": "2"}), page="1"
        )
        self.fake.add(
            "GET",
            path,
            make_response(200, [{"order_id": 1001}], {"X-Pages": "2"}),
            page="2",
        )
        pages = list(get_region_market_orders_pages(10000002, type_id=34))
        self.assertEqual(pages, [full, [{"order_id": 1001}]])
        self.assertEqual(
            self.fake.requested(),
            [
                ("GET", path, (("page", "1"), ("type_id", "34"))),
                ("GET", path, (("page", "2"), ("type_id", "34"))),
            ],
        )

    def test_stops_at_x_pages_even_on_a_full_page(self):
        path = "/markets/10000002/orders/"
        full = [{"order_id": i} for i in range(1000)]
        self.fake.add(
            "GET", path, make_response(200, full, {"X-Pages": "1"}), page="1"
        )
        pages = list(get_region_market_orders_pages(10000002))
        self.assertEqual(pages, [full])
        self.assertEqual(len(self.fake.calls), 1)

    def test_reads_past_a_short_page_when_x_pages_says_so(self):
        path = "/markets/10000002/orders/"
        for page in ("1", "2"):
            self.fake.add(
                "GET",
                path,
                make_response(200, [{"p": page}], {"X-Pages": "2"}),
                page=page,
            )
        pages = list(get_region_market_orders_pages(10000002))
        self.assertEqual(pages, [[{"p": "1"}], [{"p": "2"}]])

    def test_error_yields_none(self):
        self.fake.add(
            "GET", "/markets/10000002/orders/", make_response(500, None)
        )
        self.assertEqual(
            list(get_region_market_orders_pages(10000002)), [None]
        )
