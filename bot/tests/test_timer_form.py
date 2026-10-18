"""The /timer modal must not block the bot's event loop."""

import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TimerFormTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_submit_runs_off_the_event_loop(self):
        # pylint: disable=import-outside-toplevel
        from app.timer_form import TimerForm

        loop_thread = threading.current_thread()
        seen = {}

        def fake_submit(request):
            seen["thread"] = threading.current_thread()
            seen["request"] = request
            return {}

        form = TimerForm()
        form.timer._value = "Sosala - Fort\n0\nReinforced until 2026.10.20"
        form.corporation_name._value = "Some Corp"
        form.structure_type._value = "Fortizar"
        form.structure_state._value = "armor"
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()

        with patch("app.timer_form.submit_timer", side_effect=fake_submit):
            await form.on_submit(interaction)

        self.assertIsNot(loop_thread, seen["thread"])
        self.assertEqual("fortizar", seen["request"].type.value)
        self.assertEqual("armor", seen["request"].state.value)
        interaction.response.send_message.assert_awaited_once_with(
            "Timer submitted!"
        )
