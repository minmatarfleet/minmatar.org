"""
Guards for how the backend talks to Discord.

1. Request handlers (endpoints, routers, views) do not call Discord. Build the
   message in the handler and queue it with `discord.outbox`, or use the
   notifications service. DiscordClient retries rate limits with backoff, so
   an inline call can hold a web worker for minutes.
2. Direct DMs (`.send_dm(`) live in a short, reviewed list of modules.
   Person-directed messages should normally go through
   `notifications.service.notify_user`, which gives members preferences,
   rate limits and a delivery record. See docs/notifications/README.md.

Adding to either allowlist is a deliberate choice: say why next to the entry.
"""

from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parent.parent

# Request-path modules that may still use DiscordClient, and why.
REQUEST_PATH_ALLOWLIST = {
    # OAuth code exchange and guild join: the response depends on it.
    "discord/views.py": "OAuth login",
    "users/router.py": "OAuth login",
    "tribes/endpoints/external_guild/get_external_guild_callback.py": (
        "OAuth guild join"
    ),
    # Service-account (bot) call; the ticket only closes if the thread did.
    "help_tickets/router.py": "help ticket thread close",
    # Staff-only admin and diagnostics, not member-facing traffic.
    "users/admin.py": "admin role delete",
    "tech/router.py": "tech diagnostics: list roles",
}

# Modules that may send a DM directly, and why.
SEND_DM_ALLOWLIST = {
    "discord/client.py": "defines send_dm",
    "discord/outbox.py": "queued transport for request-built messages",
    "notifications/channels.py": "notifications Discord channel",
    # Celery-side senders whose callers need the send result right away, or
    # whose messages carry buttons/links the notifications embed cannot.
    "fleets/helpers/npsi_ingest.py": "action buttons",
    "fleets/helpers/missing_signups.py": "FC sees delivered/failed counts",
    "reddit/scheduling.py": "slot status records whether the CEO was told",
    "tribes/helpers/external_guild.py": "OAuth join link and chief alerts",
    "fittings/helpers/notifications.py": "doctrine change digest (Celery)",
}

REQUEST_PATH_TOKENS = ("DiscordClient", ".send_dm(", ".create_message(")


def _product_files():
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        parts = rel.split("/")
        if any(p in ("migrations", "tests", "management") for p in parts):
            continue
        name = parts[-1]
        if name.startswith("test") or name.endswith("tests.py"):
            continue
        yield rel, path


def _is_request_path(rel: str) -> bool:
    parts = rel.split("/")
    return (
        "endpoints" in parts
        or parts[-1] in ("router.py", "views.py", "admin.py")
        or "routers" in parts
    )


class DiscordRequestPathGuardTestCase(SimpleTestCase):
    def test_request_handlers_do_not_call_discord(self):
        offenders = []
        for rel, path in _product_files():
            if not _is_request_path(rel) or rel in REQUEST_PATH_ALLOWLIST:
                continue
            source = path.read_text(encoding="utf-8")
            if any(token in source for token in REQUEST_PATH_TOKENS):
                offenders.append(rel)
        self.assertEqual(
            [],
            sorted(offenders),
            "Request handlers must not call Discord inline. Queue the "
            "message with discord.outbox (or notify_user) instead.",
        )

    def test_direct_dms_only_from_reviewed_modules(self):
        offenders = []
        for rel, path in _product_files():
            if rel in SEND_DM_ALLOWLIST:
                continue
            if ".send_dm(" in path.read_text(encoding="utf-8"):
                offenders.append(rel)
        self.assertEqual(
            [],
            sorted(offenders),
            "Send person-directed DMs with notifications.service.notify_user "
            "(or discord.outbox.queue_dm with a reason in SEND_DM_ALLOWLIST).",
        )

    def test_allowlists_have_no_stale_entries(self):
        for rel in list(REQUEST_PATH_ALLOWLIST) + list(SEND_DM_ALLOWLIST):
            self.assertTrue((BACKEND / rel).exists(), rel)
