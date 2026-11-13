"""Discord UI for mentor class DMs.

Pass (mentor, request DM), I can't make it / Cancel the class and I'll be
there (both, booked and reminder DMs), and the 48-hour feedback buttons:
each answer opens a short form for an optional note that only alliance
leadership sees.
"""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    MENTOR_CANCEL_PREFIX,
    MENTOR_CANCEL_TEMPLATE,
    MENTOR_CLOSE_PREFIXES,
    MENTOR_CLOSE_TEMPLATES,
    MENTOR_CONFIRM_PREFIX,
    MENTOR_CONFIRM_TEMPLATE,
    MENTOR_PASS_PREFIX,
    MENTOR_PASS_TEMPLATE,
    MENTOR_RATE_PREFIXES,
    MENTOR_RATE_TEMPLATES,
    custom_id,
)

from .service import MentorActionError, act, send_feedback

logger = logging.getLogger(__name__)

FAILED = "Couldn't do that. Try again in a bit."


async def _act(interaction: discord.Interaction, request_id: int, action: str):
    await interaction.response.defer(ephemeral=True)
    try:
        message = await asyncio.to_thread(act, request_id, action, interaction.user.id)
    except MentorActionError as exc:
        message = str(exc)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Mentor %s failed for request %s", action, request_id)
        message = FAILED
    await interaction.followup.send(message, ephemeral=True)


class _ActionButton:
    """Shared behaviour; each subclass is a DynamicItem with a template."""

    action = ""
    label = ""
    prefix = ""
    style = discord.ButtonStyle.secondary

    def __init__(self, request_id: int):
        super().__init__(
            discord.ui.Button(
                label=self.label,
                style=self.style,
                custom_id=custom_id(self.prefix, request_id),
            )
        )
        self.request_id = request_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["request_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _act(interaction, self.request_id, self.action)


class PassButton(
    _ActionButton,
    discord.ui.DynamicItem[discord.ui.Button],
    template=MENTOR_PASS_TEMPLATE,
):
    action, label, prefix = "pass", "Pass", MENTOR_PASS_PREFIX


class CancelButton(
    _ActionButton,
    discord.ui.DynamicItem[discord.ui.Button],
    template=MENTOR_CANCEL_TEMPLATE,
):
    action, label, prefix = "cancel", "Cancel the class", MENTOR_CANCEL_PREFIX


class ConfirmButton(
    _ActionButton,
    discord.ui.DynamicItem[discord.ui.Button],
    template=MENTOR_CONFIRM_TEMPLATE,
):
    action, label, prefix = "confirm", "I'll be there", MENTOR_CONFIRM_PREFIX
    style = discord.ButtonStyle.success


class FeedbackModal(discord.ui.Modal):
    note = discord.ui.TextInput(
        label="Anything leadership should know?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1500,
    )

    def __init__(self, request_id: int, answer: str, title: str):
        super().__init__(title=title, timeout=600)
        self.request_id = request_id
        self.answer = answer

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            message = await asyncio.to_thread(
                send_feedback,
                self.request_id,
                interaction.user.id,
                self.answer,
                str(self.note.value or ""),
            )
        except MentorActionError as exc:
            message = str(exc)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Mentor feedback failed for request %s", self.request_id)
            message = FAILED
        await interaction.followup.send(message, ephemeral=True)


def _feedback_button(answer: str, label: str, prefix: str, tmpl: str, title):
    class _Button(discord.ui.DynamicItem[discord.ui.Button], template=tmpl):
        def __init__(self, request_id: int):
            super().__init__(
                discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.secondary,
                    custom_id=custom_id(prefix, request_id),
                )
            )
            self.request_id = request_id

        @classmethod
        async def from_custom_id(
            cls,
            interaction: discord.Interaction,
            item: discord.ui.Button,
            match: re.Match[str],
            /,
        ):
            return cls(int(match["request_id"]))

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(
                FeedbackModal(self.request_id, answer, title)
            )

    _Button.__name__ = f"Mentor{answer.title().replace('_', '')}Button"
    return _Button


RATE_LABELS = {
    "really": "Really helped",
    "bit": "Helped a bit",
    "not": "Didn't help",
    "didnt_happen": "It didn't happen",
}
CLOSE_LABELS = {
    "done": "Yes, done",
    "another": "Yes, needs another class",
    "no_show": "No-show",
    "moved": "We moved it",
}

RATE_BUTTONS = {
    answer: _feedback_button(
        answer,
        RATE_LABELS[answer],
        MENTOR_RATE_PREFIXES[answer],
        MENTOR_RATE_TEMPLATES[answer],
        "Not shared with your mentor",
    )
    for answer in MENTOR_RATE_PREFIXES
}
CLOSE_BUTTONS = {
    answer: _feedback_button(
        answer,
        CLOSE_LABELS[answer],
        MENTOR_CLOSE_PREFIXES[answer],
        MENTOR_CLOSE_TEMPLATES[answer],
        "Notes for leadership",
    )
    for answer in MENTOR_CLOSE_PREFIXES
}


def register_mentor_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(
        PassButton,
        CancelButton,
        ConfirmButton,
        *RATE_BUTTONS.values(),
        *CLOSE_BUTTONS.values(),
    )
