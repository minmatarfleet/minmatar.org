"""/campaign-timer and /campaign-structure send what the modal holds."""

import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def _interaction():
    interaction = MagicMock()
    interaction.guild_id = 555
    interaction.user.id = 9001
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class CampaignReportTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_timer_report_posts_off_the_event_loop(self):
        # pylint: disable=import-outside-toplevel
        from app.campaign_reports.api import ReportResult
        from app.campaign_reports.views import TimerReportModal

        loop_thread = threading.current_thread()
        seen = {}

        def fake_submit(request):
            seen["thread"] = threading.current_thread()
            seen["request"] = request
            return ReportResult(
                message="Timer added.", campaign="Push", url="https://x/t"
            )

        modal = TimerReportModal("fortizar", "armor", "")
        modal.paste._value = "Kamela - Fort\n0 m\nReinforced until 2026.11.23"
        modal.corporation_name._value = "Bad Guys"
        modal.alliance_name._value = ""
        interaction = _interaction()

        with patch(
            "app.campaign_reports.views.submit_report", side_effect=fake_submit
        ):
            await modal.on_submit(interaction)

        self.assertIsNot(loop_thread, seen["thread"])
        request = seen["request"]
        self.assertEqual(request.kind, "timer")
        self.assertEqual(request.guild_id, 555)
        self.assertEqual(request.discord_user_id, 9001)
        self.assertEqual(request.timer_state, "armor")
        self.assertEqual(request.corporation_name, "Bad Guys")
        interaction.followup.send.assert_awaited_once_with(
            "Timer added.\nhttps://x/t", ephemeral=True
        )

    async def test_refusal_is_shown_to_the_reporter_only(self):
        # pylint: disable=import-outside-toplevel
        from app.campaign_reports.api import ReportError
        from app.campaign_reports.views import StructureReportModal

        modal = StructureReportModal("astrahus", "")
        modal.paste._value = "Kamela - Astra"
        modal.corporation_name._value = ""
        modal.alliance_name._value = ""
        modal.reinforce_hour._value = "19"
        interaction = _interaction()

        with patch(
            "app.campaign_reports.views.submit_report",
            side_effect=ReportError("Only the campaign's Recon"),
        ) as submit:
            await modal.on_submit(interaction)

        self.assertEqual(submit.call_args.args[0].reinforce_hour, 19)
        interaction.followup.send.assert_awaited_once_with(
            "Only the campaign's Recon", ephemeral=True
        )

    async def test_bad_hour_is_refused_before_the_api(self):
        # pylint: disable=import-outside-toplevel
        from app.campaign_reports.views import StructureReportModal

        modal = StructureReportModal("astrahus", "")
        modal.paste._value = "Kamela - Astra"
        modal.corporation_name._value = ""
        modal.alliance_name._value = ""
        modal.reinforce_hour._value = "7pm"
        interaction = _interaction()

        with patch("app.campaign_reports.views.submit_report") as submit:
            await modal.on_submit(interaction)

        submit.assert_not_called()
        interaction.response.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
