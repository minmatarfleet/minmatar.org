"""The feedback DM's Answer button opens the form as a Discord pop-up."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test")
os.environ.setdefault("MINMATAR_API_TOKEN", "test")  # pragma: allowlist secret


def _form(*, with_why=True, answers=None):
    questions = [
        {
            "key": "felt",
            "short": "These invites felt…",
            "prompt": "Most of the time, these invites felt…",
            "kind": "single",
            "max": 1,
            "choices": [
                {"key": "glad", "label": "Glad I was asked"},
                {"key": "fine", "label": "Fine"},
            ],
        },
        {
            "key": "sitting_out",
            "short": "Sitting out felt like…",
            "prompt": "Which of these is closest for Sitting out?",
            "kind": "single",
            "max": 1,
            "choices": [{"key": "normal", "label": 'A normal "not this time"'}],
        },
    ]
    if with_why:
        questions.append(
            {
                "key": "why",
                "short": "Why the open ones stayed open",
                "prompt": "On the ones still open, what was most often going on?",
                "kind": "single",
                "max": 1,
                "choices": [
                    {"key": "later", "label": "I meant to decide later"},
                    {"key": "other", "label": "Other"},
                ],
            }
        )
    questions.append(
        {
            "key": "improve",
            "short": "What would have mattered",
            "prompt": "Which of these would have mattered for the invites above?",
            "kind": "multi",
            "max": 2,
            "choices": [
                {"key": "fewer", "label": "Fewer of them"},
                {"key": "maybe", "label": "A way to say maybe"},
                {"key": "nothing", "label": "Nothing. They were fine"},
            ],
        }
    )
    return {
        "state": "form",
        "questions": questions,
        "answers": answers
        or {"felt": "", "sitting_out": "", "why": "", "why_text": "", "improve": [], "comment": ""},
        "comment_heading": "One thing to change",
        "comment_placeholder": "Optional. A sentence is enough.",
        "list_heading": "Your invites, last few weeks.",
        "invites": [
            {"when": "Wed 11 Nov, 03:10", "title": "Amamake plex defense", "answer_label": "No answer"},
            {"when": "Sun 8 Nov, 03:10", "title": "Sunday roam", "answer_label": "In"},
        ],
    }


class FeedbackModalTest(unittest.IsolatedAsyncioTestCase):
    async def test_five_fields_with_the_open_invites_question(self):
        from app.fleet_invites.feedback_form import FeedbackModal

        modal = FeedbackModal(_form())
        labels = [item.text for item in modal.children]
        self.assertEqual(
            [
                "These invites felt…",
                "Sitting out felt like…",
                "Why the open ones stayed open",
                "What would have mattered",
                "One thing to change",
            ],
            labels,
        )
        for label in modal.children:
            self.assertLessEqual(len(label.text), 45)
            self.assertLessEqual(len(label.description or ""), 100)
        improve = modal.selects["improve"]
        self.assertEqual((1, 2), (improve.min_values, improve.max_values))
        # Other's reason goes in the comment, so the comment says so.
        self.assertIn("Other", modal.children[-1].description)

    async def test_title_names_the_invites(self):
        from app.fleet_invites.feedback_form import FeedbackModal

        self.assertEqual("About your 2 fleet invites", FeedbackModal(_form()).title)

    async def test_free_slot_shows_the_invite_list_first(self):
        import discord

        from app.fleet_invites.feedback_form import FeedbackModal

        modal = FeedbackModal(_form(with_why=False))
        self.assertEqual(5, len(modal.children))
        listing = modal.children[0]
        self.assertIsInstance(listing, discord.ui.TextDisplay)
        self.assertIn("Amamake plex defense · No answer", listing.content)
        self.assertNotIn("why", modal.selects)
        self.assertIsNone(modal.children[-1].description)

    async def test_no_list_when_all_five_slots_are_questions(self):
        import discord

        from app.fleet_invites.feedback_form import FeedbackModal

        modal = FeedbackModal(_form())
        self.assertFalse(
            any(isinstance(item, discord.ui.TextDisplay) for item in modal.children)
        )

    async def test_saved_answers_are_preselected(self):
        from app.fleet_invites.feedback_form import FeedbackModal

        modal = FeedbackModal(
            _form(
                answers={
                    "felt": "fine",
                    "sitting_out": "normal",
                    "why": "later",
                    "why_text": "",
                    "improve": ["fewer", "maybe"],
                    "comment": "Shorter DMs",
                }
            )
        )
        felt = {o.value: o.default for o in modal.selects["felt"].options}
        self.assertEqual({"glad": False, "fine": True}, felt)
        improve = [o.value for o in modal.selects["improve"].options if o.default]
        self.assertEqual(["fewer", "maybe"], improve)
        self.assertEqual("Shorter DMs", modal.comment.default)

    async def test_submit_sends_the_picks_and_replies_privately(self):
        from app.fleet_invites import feedback_form

        modal = feedback_form.FeedbackModal(_form())
        modal.selects["felt"]._values = ["fine"]
        modal.selects["sitting_out"]._values = ["normal"]
        modal.selects["why"]._values = ["other"]
        modal.selects["improve"]._values = ["fewer", "maybe"]
        modal.comment._value = "Away that week"

        interaction = MagicMock()
        interaction.user.id = 4242
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        seen = {}

        def fake_save(discord_user_id, answers):
            seen["args"] = (discord_user_id, answers)
            return {"state": "thanks", "heading": "Thanks.", "body": "Saved."}

        with patch.object(feedback_form, "save_answers", side_effect=fake_save):
            await modal.on_submit(interaction)

        self.assertEqual(4242, seen["args"][0])
        self.assertEqual(
            {
                "felt": "fine",
                "sitting_out": "normal",
                "why": "other",
                "why_text": "",
                "improve": ["fewer", "maybe"],
                "comment": "Away that week",
            },
            seen["args"][1],
        )
        interaction.followup.send.assert_awaited_once_with(
            "**Thanks.**\nSaved.", ephemeral=True
        )

    async def test_rejected_save_shows_the_errors_and_the_website(self):
        from app.fleet_invites import feedback_form

        modal = feedback_form.FeedbackModal(_form(with_why=False))
        interaction = MagicMock()
        interaction.user.id = 1
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        error = feedback_form.FeedbackApiError(
            "Pick one or two that would have mattered.",
            ["Pick one or two that would have mattered."],
        )
        with patch.object(feedback_form, "save_answers", side_effect=error):
            await modal.on_submit(interaction)
        sent = interaction.followup.send.await_args.args[0]
        self.assertIn("Pick one or two", sent)
        self.assertIn(feedback_form.WEBSITE_URL, sent)


class AnswerButtonTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_round_opens_the_pop_up(self):
        from app.fleet_invites import feedback_form

        interaction = MagicMock()
        interaction.user.id = 7
        interaction.response.send_modal = AsyncMock()
        interaction.response.send_message = AsyncMock()
        with patch.object(feedback_form, "load_form", return_value=_form()):
            await feedback_form.AnswerFeedbackButton(1).callback(interaction)
        modal = interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, feedback_form.FeedbackModal)
        interaction.response.send_message.assert_not_awaited()

    async def test_closed_round_says_so_instead(self):
        from app.fleet_invites import feedback_form

        interaction = MagicMock()
        interaction.user.id = 7
        interaction.response.send_modal = AsyncMock()
        interaction.response.send_message = AsyncMock()
        closed = {"state": "closed", "heading": "This survey is closed.", "body": ""}
        with patch.object(feedback_form, "load_form", return_value=closed):
            await feedback_form.AnswerFeedbackButton(1).callback(interaction)
        interaction.response.send_modal.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once_with(
            "**This survey is closed.**", ephemeral=True
        )

    async def test_failed_load_links_the_website(self):
        from app.fleet_invites import feedback_form

        interaction = MagicMock()
        interaction.user.id = 7
        interaction.response.send_modal = AsyncMock()
        interaction.response.send_message = AsyncMock()
        with patch.object(feedback_form, "load_form", side_effect=TimeoutError()):
            await feedback_form.AnswerFeedbackButton(1).callback(interaction)
        sent = interaction.response.send_message.await_args.args[0]
        self.assertIn(feedback_form.WEBSITE_URL, sent)
