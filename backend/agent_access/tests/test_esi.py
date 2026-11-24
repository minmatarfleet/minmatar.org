import json
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from esi.errors import TokenInvalidError
from esi.models import Scope, Token

from agent_access.keys import create_key
from agent_access.models import (
    AgentEsiCall,
    AgentEsiCharacter,
    AgentEsiSettings,
    AgentKey,
)
from eveonline.models import EveCharacter
from eveonline.tests.fake_esi_http import FakeEsi, make_response

URL = "/api/agent/esi/mcp"
CHARACTER = 2112345678
OTHER = 2112345679
ASSETS = f"/characters/{CHARACTER}/assets/"


class EsiMcpTestCase(TestCase):
    def setUp(self):
        self.key, self.raw = create_key("test", can_use_esi=True)
        AgentEsiCharacter.objects.create(
            key=self.key, character_id=CHARACTER, note="debugging"
        )
        self.token = Token.objects.create(
            character_id=CHARACTER, character_name="Pilot"
        )
        self.token.scopes.add(
            Scope.objects.create(name="esi-assets.read_assets.v1")
        )
        EveCharacter.objects.create(
            character_id=CHARACTER,
            character_name="Pilot",
            corporation_id=98000001,
            token=self.token,
        )
        patcher = mock.patch.object(
            Token, "valid_access_token", return_value="access-123"
        )
        self.valid_access_token = patcher.start()
        self.addCleanup(patcher.stop)
        self.esi = FakeEsi().install(self)

    def rpc(self, method, params=None, raw=None, **headers):
        body = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        return self.client.post(
            URL,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw or self.raw}",
            **headers,
        )

    def call(self, name, **arguments):
        response = self.rpc(
            "tools/call", {"name": name, "arguments": arguments}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["result"]

    def refused(self, name, **arguments) -> str:
        result = self.call(name, **arguments)
        self.assertTrue(result["isError"], result)
        self.assertFalse(self.esi.calls, "no ESI call on a refusal")
        return result["content"][0]["text"]


class AuthTests(EsiMcpTestCase):
    def test_key_without_esi_access_is_not_found(self):
        _, raw = create_key("discord only")
        self.assertEqual(self.rpc("ping", raw=raw).status_code, 404)

    def test_no_key_is_not_found(self):
        response = self.client.post(
            URL, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_revoked_key_is_not_found(self):
        AgentKey.objects.filter(pk=self.key.pk).update(
            revoked_at=timezone.now()
        )
        self.assertEqual(self.rpc("ping").status_code, 404)

    def test_browser_requests_are_refused(self):
        response = self.rpc("ping", HTTP_ORIGIN="https://evil.example")
        self.assertEqual(response.status_code, 403)

    def test_kill_switch(self):
        AgentEsiSettings.objects.update_or_create(
            pk=1, defaults={"enabled": False}
        )
        self.assertEqual(self.rpc("ping").status_code, 403)

    def test_initialize_names_the_esi_server(self):
        result = self.rpc(
            "initialize", {"protocolVersion": "2025-06-18"}
        ).json()["result"]
        self.assertEqual(result["serverInfo"]["name"], "minmatar-esi")
        tools = self.rpc("tools/list").json()["result"]["tools"]
        self.assertEqual(
            [t["name"] for t in tools],
            ["list_characters", "esi_get", "esi_post"],
        )
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))


class ListCharactersTests(EsiMcpTestCase):
    def test_lists_granted_characters_with_scopes(self):
        AgentEsiCharacter.objects.create(
            key=self.key,
            character_id=OTHER,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        result = self.call("list_characters")["structuredContent"]
        self.assertEqual(len(result["characters"]), 1)
        row = result["characters"][0]
        self.assertEqual(row["character_id"], CHARACTER)
        self.assertEqual(row["character_name"], "Pilot")
        self.assertEqual(row["scopes"], ["esi-assets.read_assets.v1"])
        self.assertEqual(row["note"], "debugging")


class EsiGetTests(EsiMcpTestCase):
    def test_calls_esi_with_the_characters_token(self):
        self.esi.add(
            "GET",
            ASSETS,
            make_response(
                body=[{"item_id": 1, "type_id": 587}],
                headers={"X-Pages": "3", "Expires": "soon"},
            ),
            page="2",
        )
        result = self.call(
            "esi_get", path=ASSETS, character_id=CHARACTER, page=2
        )
        self.assertFalse(result["isError"], result)
        out = result["structuredContent"]
        self.assertEqual(out["data"], [{"item_id": 1, "type_id": 587}])
        self.assertEqual(out["pages"], 3)
        sent = self.esi.calls[0]
        self.assertEqual(sent["method"], "GET")
        self.assertTrue(sent["url"].startswith("https://esi.evetech.net/"))
        self.assertNotIn("/latest", sent["url"])
        self.assertEqual(sent["headers"]["Authorization"], "Bearer access-123")
        self.assertIn("X-Compatibility-Date", sent["headers"])
        row = AgentEsiCall.objects.get()
        self.assertTrue(row.ok)
        self.assertEqual(row.character_id, CHARACTER)
        self.assertEqual(row.path, ASSETS)
        self.assertEqual(row.esi_status, 200)

    def test_public_route_sends_no_token(self):
        self.esi.add("GET", "/status/", make_response(body={"players": 1}))
        result = self.call("esi_get", path="/status/")
        self.assertFalse(result["isError"], result)
        self.assertNotIn("Authorization", self.esi.calls[0]["headers"])

    def test_ungranted_character_is_refused(self):
        text = self.refused(
            "esi_get",
            path=f"/characters/{OTHER}/assets/",
            character_id=OTHER,
        )
        self.assertIn("no grant", text)
        self.assertFalse(AgentEsiCall.objects.get().ok)

    def test_expired_grant_is_refused(self):
        AgentEsiCharacter.objects.update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.refused("esi_get", path=ASSETS, character_id=CHARACTER)

    def test_route_for_another_character_is_refused(self):
        text = self.refused(
            "esi_get",
            path=f"/characters/{OTHER}/wallet/",
            character_id=CHARACTER,
        )
        self.assertIn("must name the character_id", text)

    def test_mail_is_blocked_by_default(self):
        text = self.refused(
            "esi_get",
            path=f"/characters/{CHARACTER}/mail/",
            character_id=CHARACTER,
        )
        self.assertIn("blocked", text)

    def test_bad_paths_are_refused(self):
        for path in (
            "https://evil.example/x",
            "/characters/../corporations/1/",
            "/latest/status/",
            "/v4/status/",
            "/status/?page=2",
            "//status/",
            "status/",
        ):
            with self.subTest(path=path):
                self.refused("esi_get", path=path)

    def test_suspended_character_is_refused(self):
        EveCharacter.objects.update(esi_suspended=True)
        text = self.refused("esi_get", path=ASSETS, character_id=CHARACTER)
        self.assertIn("suspended", text)

    def test_invalid_token_is_refused(self):
        self.valid_access_token.side_effect = TokenInvalidError()
        text = self.refused("esi_get", path=ASSETS, character_id=CHARACTER)
        self.assertIn("no longer works", text)

    def test_missing_scopes_are_refused(self):
        text = self.refused(
            "esi_get",
            path=f"/characters/{CHARACTER}/wallet/",
            character_id=CHARACTER,
            scopes=["esi-wallet.read_character_wallet.v1"],
        )
        self.assertIn("scopes", text)

    def test_esi_error_is_a_tool_error_and_logged(self):
        self.esi.add(
            "GET",
            ASSETS,
            make_response(status=403, body={"error": "token not valid"}),
        )
        result = self.call("esi_get", path=ASSETS, character_id=CHARACTER)
        self.assertTrue(result["isError"])
        self.assertIn("403", result["content"][0]["text"])
        row = AgentEsiCall.objects.get()
        self.assertFalse(row.ok)
        self.assertEqual(row.esi_status, 403)

    def test_large_answers_are_refused(self):
        self.esi.add(
            "GET", ASSETS, make_response(body=[{"x": "y" * 1000}] * 400)
        )
        result = self.call("esi_get", path=ASSETS, character_id=CHARACTER)
        self.assertTrue(result["isError"])
        self.assertIn("KB", result["content"][0]["text"])

    def test_rate_limit_per_minute(self):
        AgentEsiSettings.objects.update_or_create(
            pk=1, defaults={"calls_per_minute": 1}
        )
        self.esi.add("GET", "/status/", make_response(body={}))
        self.assertFalse(self.call("esi_get", path="/status/")["isError"])
        result = self.call("esi_get", path="/status/")
        self.assertTrue(result["isError"])
        self.assertIn("rate limit", result["content"][0]["text"])
        self.assertEqual(len(self.esi.calls), 1)

    def test_low_error_budget_is_refused(self):
        with mock.patch(
            "agent_access.esi_tools.esi_budget.error_budget", return_value=5
        ):
            text = self.refused("esi_get", path="/status/")
        self.assertIn("error budget", text)


class EsiPostTests(EsiMcpTestCase):
    def test_universe_names(self):
        self.esi.add(
            "POST",
            "/universe/names/",
            make_response(body=[{"id": 30002537, "name": "Amamake"}]),
        )
        result = self.call(
            "esi_post", path="/universe/names/", body=[30002537]
        )
        self.assertFalse(result["isError"], result)
        self.assertEqual(json.loads(self.esi.calls[0]["body"]), [30002537])
        self.assertNotIn("Authorization", self.esi.calls[0]["headers"])

    def test_other_post_routes_are_refused(self):
        text = self.refused(
            "esi_post",
            path=f"/characters/{CHARACTER}/fittings/",
            body=[1],
        )
        self.assertIn("read-only POST", text)

    def test_body_type_is_checked(self):
        self.refused("esi_post", path="/universe/names/", body=["Amamake"])
        self.refused("esi_post", path="/universe/ids/", body=[1])


class CommandTests(TestCase):
    def test_grant_and_revoke(self):
        key, _ = create_key("cli")
        out = StringIO()
        call_command(
            "agent_key",
            "esi-grant",
            key.key_prefix,
            str(CHARACTER),
            "--note",
            "ticket 12",
            "--days",
            "7",
            stdout=out,
        )
        key.refresh_from_db()
        self.assertTrue(key.can_use_esi)
        grant = AgentEsiCharacter.objects.get(key=key)
        self.assertEqual(grant.note, "ticket 12")
        self.assertIsNotNone(grant.expires_at)
        call_command(
            "agent_key",
            "esi-revoke",
            key.key_prefix,
            str(CHARACTER),
            stdout=out,
        )
        self.assertFalse(AgentEsiCharacter.objects.exists())

    def test_create_with_esi(self):
        call_command("agent_key", "create", "x", "--esi", stdout=StringIO())
        self.assertTrue(AgentKey.objects.get().can_use_esi)
