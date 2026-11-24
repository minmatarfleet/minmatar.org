import json
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from agent_access import tools
from agent_access.keys import create_key
from agent_access.models import (
    AgentDiscordCall,
    AgentDiscordPostTarget,
    AgentDiscordReadBlock,
    AgentDiscordSettings,
)

URL = "/api/agent/discord/mcp"
GUILD = "100000000000000001"
OTHER_GUILD = "100000000000000002"
CATEGORY = "200000000000000001"
CHANNEL = "200000000000000002"
THREAD = "200000000000000003"
DM = "200000000000000009"
MESSAGE = "300000000000000001"
USER = "400000000000000001"

CHANNELS = {
    CATEGORY: {"id": CATEGORY, "guild_id": GUILD, "type": 4, "name": "staff"},
    CHANNEL: {
        "id": CHANNEL,
        "guild_id": GUILD,
        "type": 0,
        "name": "help",
        "parent_id": CATEGORY,
    },
    THREAD: {
        "id": THREAD,
        "guild_id": GUILD,
        "type": 12,
        "name": "ticket",
        "parent_id": CHANNEL,
        "thread_metadata": {"archived": True, "locked": False},
    },
    DM: {"id": DM, "type": 1},
}


def fake_get(path, params=None):
    if path.startswith("/channels/") and path.count("/") == 2:
        return CHANNELS[path.split("/")[2]]
    if path.endswith("/messages"):
        return [
            {
                "id": MESSAGE,
                "channel_id": path.split("/")[2],
                "author": {"id": USER, "username": "pilot"},
                "content": "My fleet page is broken",
                "attachments": [
                    {"id": "1", "filename": "shot.png", "url": "https://x"}
                ],
            }
        ]
    if path == "/users/@me/guilds":
        return [
            {"id": GUILD, "name": "Minmatar Fleet", "permissions": "8"},
            {"id": OTHER_GUILD, "name": "Other", "permissions": "0"},
        ]
    raise AssertionError(f"unexpected GET {path}")


class McpTestCase(TestCase):
    def setUp(self):
        self.key, self.raw = create_key("test")
        patcher = mock.patch.object(
            tools.discord_api, "get", side_effect=fake_get
        )
        self.get = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(
            tools.discord_api,
            "post_message",
            return_value={"id": "500000000000000001", "channel_id": THREAD},
        )
        self.post = patcher.start()
        self.addCleanup(patcher.stop)

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


class AuthTests(McpTestCase):
    def test_no_key_is_not_found(self):
        response = self.client.post(
            URL, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_key_is_not_found(self):
        self.assertEqual(self.rpc("ping", raw="mfa_nope").status_code, 404)

    def test_a_pilot_jwt_is_not_found(self):
        self.assertEqual(
            self.rpc("ping", raw="eyJhbGciOi.x.y").status_code, 404
        )

    def test_revoked_key_is_not_found(self):
        self.key.revoked_at = timezone.now()
        self.key.save()
        self.assertEqual(self.rpc("ping").status_code, 404)

    def test_expired_key_is_not_found(self):
        self.key.expires_at = timezone.now() - timedelta(minutes=1)
        self.key.save()
        self.assertEqual(self.rpc("ping").status_code, 404)

    def test_browser_requests_are_refused(self):
        response = self.rpc("ping", HTTP_ORIGIN="https://evil.example")
        self.assertEqual(response.status_code, 403)

    def test_kill_switch(self):
        AgentDiscordSettings.objects.update_or_create(
            pk=1, defaults={"enabled": False}
        )
        self.assertEqual(self.rpc("ping").status_code, 403)

    def test_get_is_not_allowed(self):
        response = self.client.get(
            URL, HTTP_AUTHORIZATION=f"Bearer {self.raw}"
        )
        self.assertEqual(response.status_code, 405)

    def test_valid_key_records_use(self):
        self.assertEqual(self.rpc("ping").status_code, 200)
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)


class ProtocolTests(McpTestCase):
    def test_initialize(self):
        result = self.rpc(
            "initialize", {"protocolVersion": "2025-06-18"}
        ).json()["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])

    def test_notification_gets_202(self):
        response = self.client.post(
            URL,
            data=json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )
        self.assertEqual(response.status_code, 202)

    def test_tool_list_has_no_moderation_tools(self):
        listed = self.rpc("tools/list").json()["result"]["tools"]
        names = {t["name"] for t in listed}
        self.assertIn("read_messages", names)
        self.assertIn("send_message", names)
        for forbidden in (
            "ban",
            "kick",
            "role",
            "delete",
            "webhook",
            "invite",
        ):
            self.assertFalse(
                [n for n in names if forbidden in n and n != "list_roles"],
                forbidden,
            )

    def test_unknown_tool(self):
        response = self.rpc("tools/call", {"name": "ban_member"})
        self.assertEqual(response.json()["error"]["code"], -32602)

    def test_invalid_json(self):
        response = self.client.post(
            URL,
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )
        self.assertEqual(response.status_code, 400)


class ReadTests(McpTestCase):
    def test_read_messages_is_audited(self):
        result = self.call("read_messages", channel_id=THREAD, limit=500)
        self.assertFalse(result["isError"])
        message = result["structuredContent"]["messages"][0]
        self.assertEqual(message["content"], "My fleet page is broken")
        self.assertEqual(message["attachments"][0]["filename"], "shot.png")
        self.get.assert_any_call(
            f"/channels/{THREAD}/messages", {"limit": 100}
        )
        call = AgentDiscordCall.objects.get()
        self.assertEqual(
            (call.tool, call.ok, call.guild_id, call.channel_id),
            ("read_messages", True, GUILD, THREAD),
        )

    def test_dm_channels_are_refused(self):
        result = self.call("read_messages", channel_id=DM)
        self.assertTrue(result["isError"])
        self.assertFalse(AgentDiscordCall.objects.get().ok)

    def test_bad_id_is_refused(self):
        result = self.call("read_messages", channel_id="../guilds/1")
        self.assertTrue(result["isError"])

    def test_blocked_category_blocks_its_threads(self):
        AgentDiscordReadBlock.objects.create(
            guild_id=GUILD, channel_id=CATEGORY
        )
        result = self.call("read_messages", channel_id=THREAD)
        self.assertTrue(result["isError"])
        self.assertIn("blocked", result["content"][0]["text"])

    def test_list_channels_queries_targets_once(self):
        AgentDiscordPostTarget.objects.create(
            guild_id=GUILD, channel_id=CHANNEL
        )
        channels = [CHANNELS[CATEGORY], CHANNELS[CHANNEL]] * 20
        self.get.side_effect = lambda path, params=None: channels
        ctx = tools.Context(key=self.key, settings=AgentDiscordSettings.get())
        # Server block check, channel blocks, post targets: not per channel.
        with self.assertNumQueries(3):
            listed = tools.list_channels(ctx, {"guild_id": GUILD})
        self.assertEqual(len(listed["channels"]), 40)
        self.assertTrue(listed["channels"][1]["can_post"])

    def test_blocked_server_is_hidden(self):
        AgentDiscordReadBlock.objects.create(guild_id=OTHER_GUILD)
        servers = self.call("list_servers")["structuredContent"]["servers"]
        self.assertEqual([s["id"] for s in servers], [GUILD])
        self.assertTrue(servers[0]["bot_is_admin"])

    def test_only_one_anchor(self):
        result = self.call(
            "read_messages", channel_id=THREAD, before=MESSAGE, after=MESSAGE
        )
        self.assertTrue(result["isError"])


class WriteTests(McpTestCase):
    def send(self, **extra):
        return self.call(
            "send_message", channel_id=THREAD, content="Fixed in #42", **extra
        )

    def test_refused_without_a_post_target(self):
        result = self.send()
        self.assertTrue(result["isError"])
        self.post.assert_not_called()

    def test_thread_under_an_allowed_channel(self):
        AgentDiscordPostTarget.objects.create(
            guild_id=GUILD, channel_id=CHANNEL
        )
        result = self.send(mention_user_ids=[USER])
        self.assertFalse(result["isError"])
        payload = self.post.call_args.args[1]
        self.assertEqual(
            payload["allowed_mentions"],
            {"parse": [], "users": [USER], "replied_user": False},
        )
        self.assertTrue(AgentDiscordCall.objects.get().is_write)

    def test_thread_excluded_when_threads_are_off(self):
        AgentDiscordPostTarget.objects.create(
            guild_id=GUILD, channel_id=CHANNEL, include_threads=False
        )
        self.assertTrue(self.send()["isError"])

    def test_read_only_key(self):
        AgentDiscordPostTarget.objects.create(guild_id=GUILD)
        self.key.can_write = False
        self.key.save()
        self.assertTrue(self.send()["isError"])
        self.post.assert_not_called()

    def test_writes_switched_off(self):
        AgentDiscordPostTarget.objects.create(guild_id=GUILD)
        AgentDiscordSettings.objects.update_or_create(
            pk=1, defaults={"writes_enabled": False}
        )
        self.assertTrue(self.send()["isError"])

    def test_rate_limit(self):
        AgentDiscordPostTarget.objects.create(guild_id=GUILD)
        AgentDiscordSettings.objects.update_or_create(
            pk=1, defaults={"writes_per_minute": 2}
        )
        self.assertFalse(self.send()["isError"])
        self.assertFalse(self.send()["isError"])
        with self.assertLogs("agent_access.mcp", "ERROR"):
            self.assertTrue(self.send()["isError"])
        self.assertEqual(self.post.call_count, 2)

    def test_too_long(self):
        AgentDiscordPostTarget.objects.create(guild_id=GUILD)
        result = self.call(
            "send_message", channel_id=THREAD, content="x" * 2001
        )
        self.assertTrue(result["isError"])


class CommandTests(TestCase):
    def test_create_list_revoke(self):
        out = StringIO()
        call_command("agent_key", "create", "cloud", "--read-only", stdout=out)
        raw = out.getvalue().strip().splitlines()[-1]
        self.assertTrue(raw.startswith("mfa_"))
        response = self.client.post(
            URL,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )
        self.assertEqual(response.status_code, 200)

        call_command("agent_key", "revoke", raw[:12], stdout=StringIO())
        response = self.client.post(
            URL,
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )
        self.assertEqual(response.status_code, 404)
