"""The /fleet-invite-feedback command tells the API, then replies."""

import os
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test")
os.environ.setdefault("MINMATAR_API_TOKEN", "test")  # pragma: allowlist secret


class FleetInviteFeedbackCommandTest(unittest.IsolatedAsyncioTestCase):
    async def test_reply_is_private_and_off_the_event_loop(self):
        from app.fleet_invites.feedback import handle_fleet_invite_feedback

        loop_thread = threading.current_thread()
        seen = {}

        def fake_send(discord_user_id, action, confirm):
            seen["thread"] = threading.current_thread()
            seen["args"] = (discord_user_id, action, confirm)
            return "Nothing is sent. This is who would get the form."

        interaction = MagicMock()
        interaction.user.id = 4242
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch("app.fleet_invites.feedback.send_feedback", side_effect=fake_send):
            await handle_fleet_invite_feedback(interaction, "preview", False)

        self.assertIsNot(loop_thread, seen["thread"])
        self.assertEqual((4242, "preview", False), seen["args"])
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once_with(
            "Nothing is sent. This is who would get the form.",
            ephemeral=True,
        )
