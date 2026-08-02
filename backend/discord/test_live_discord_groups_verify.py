"""
Opt-in live Discord fail-closed verification.

Skipped unless RUN_DISCORD_LIVE_VERIFY=1. Uses SimpleTestCase so Django does
not wrap the run in a transaction (that would roll back DB while leaving
Discord roles behind).

Run against the real local DB + test guild (never settings_test / never prod):

  RUN_DISCORD_LIVE_VERIFY=1 \\
  DISCORD_LIVE_VERIFY_USER=bearthatcares \\
  DISCORD_LIVE_VERIFY_GUILD_ID=1459994254427291781 \\
  pipenv run python manage.py test discord.test_live_discord_groups_verify \\
    --settings=app.settings

Prefer the management command for day-to-day use:

  pipenv run python manage.py verify_discord_groups \\
    --username bearthatcares \\
    --guild-id 1459994254427291781 \\
    --i-understand-this-hits-live-discord
"""

from __future__ import annotations

import os
import unittest

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from discord.live_verify import (
    ENV_ENABLE,
    LiveVerifyError,
    PRODUCTION_DISCORD_GUILD_IDS,
    assert_live_verify_allowed,
    run_live_discord_groups_verify,
)


class LiveDiscordGroupsVerifySafetyTestCase(SimpleTestCase):
    """Always-on gates — must never hit live Discord."""

    def test_production_guild_refused(self):
        prod = next(iter(PRODUCTION_DISCORD_GUILD_IDS))
        with override_settings(DISCORD_GUILD_ID=prod, DISCORD_BOT_TOKEN="x"):
            with self.assertRaises(LiveVerifyError) as ctx:
                assert_live_verify_allowed(require_env=False)
            self.assertIn("production", str(ctx.exception).lower())

    def test_unknown_guild_refused(self):
        with override_settings(
            DISCORD_GUILD_ID=999999999999999999, DISCORD_BOT_TOKEN="x"
        ):
            with self.assertRaises(LiveVerifyError) as ctx:
                assert_live_verify_allowed(require_env=False)
            self.assertIn("allowlist", str(ctx.exception).lower())

    def test_env_gate_when_required(self):
        with override_settings(
            DISCORD_GUILD_ID=1459994254427291781, DISCORD_BOT_TOKEN="x"
        ):
            os.environ.pop(ENV_ENABLE, None)
            with self.assertRaises(LiveVerifyError):
                assert_live_verify_allowed(require_env=True)


@unittest.skipUnless(
    os.environ.get(ENV_ENABLE) == "1",
    f"Set {ENV_ENABLE}=1 to run live Discord verification",
)
class LiveDiscordGroupsVerifyTestCase(SimpleTestCase):
    """Full A–H matrix against live test Discord. Manual / opt-in only."""

    # Allow ORM without TestCase transaction rollback (Discord is external).
    databases = {"default"}

    def test_fail_closed_matrix_against_live_test_guild(self):
        username = os.environ.get("DISCORD_LIVE_VERIFY_USER", "").strip()
        self.assertTrue(
            username,
            "Set DISCORD_LIVE_VERIFY_USER to a guild-linked Django username",
        )
        raw_guild = os.environ.get("DISCORD_LIVE_VERIFY_GUILD_ID", "").strip()
        guild_override = int(raw_guild) if raw_guild else None
        guild_id = int(
            guild_override
            if guild_override is not None
            else settings.DISCORD_GUILD_ID
        )
        self.assertNotIn(
            guild_id,
            PRODUCTION_DISCORD_GUILD_IDS,
            "Live verify must not use the production Discord guild",
        )

        report = run_live_discord_groups_verify(
            username=username,
            require_env=True,
            guild_id=guild_override,
        )
        failed = [r for r in report.results if not r.passed]
        if failed:
            details = "\n".join(
                f"{r.case_id}: {r.notes.splitlines()[0] if r.notes else 'FAIL'}"
                for r in failed
            )
            self.fail(
                f"{len(failed)}/{len(report.results)} live verify cases failed:\n"
                f"{details}"
            )
