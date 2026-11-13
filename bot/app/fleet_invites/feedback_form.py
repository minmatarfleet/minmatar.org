"""The fleet invite feedback form as a Discord pop-up.

The feedback DM has an Answer button. Clicking it loads the pilot's form
from the API (their saved answers, and whether the open-invites question
applies) and opens a pop-up with one dropdown per question and the comment.
Submitting saves through the API, which fits the answer to the website's
rules (bot API: /fleets/invite-feedback/discord-form and discord-submit).
"""

from __future__ import annotations

import asyncio
import logging
import re

import discord
import requests

from app.custom_ids import (
    INVITE_FEEDBACK_ANSWER_PREFIX,
    INVITE_FEEDBACK_ANSWER_TEMPLATE,
    custom_id,
)
from app.settings import settings

logger = logging.getLogger(__name__)

FLEETS_BASE_URL = f"{settings.API_URL}/fleets"
AUTH_HEADERS = {
    "Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}",  # pragma: allowlist secret
}
WEBSITE_URL = f"{settings.WEB_URL}/fleets/invite-feedback/"

TITLE = "Fleet invites survey"
# Discord answers a click only within 3 seconds, and the pop-up has to be
# that answer, so the form load gets less than that.
LOAD_TIMEOUT = 2.5
# Discord's limits on a pop-up form.
MAX_FIELDS = 5
LABEL_MAX = 45
DESCRIPTION_MAX = 100
OPTION_MAX = 100
COMMENT_MAX = 280
LISTING_LIMIT = 10

OTHER_HINT = "If you picked Other above, say the reason here."
LOAD_FAILED = "The form didn't load. Try again, or answer on the website:"
SAVE_FAILED = "Your answer wasn't saved. Try again, or answer on the website:"


class FeedbackApiError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


def _post(path: str, body: dict, timeout: float) -> dict:
    response = requests.post(
        f"{FLEETS_BASE_URL}/invite-feedback/{path}",
        headers=AUTH_HEADERS,
        json=body,
        timeout=timeout,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        detail = str(payload.get("detail") or "Request failed")
        raise FeedbackApiError(detail, payload.get("errors"))
    return payload


def load_form(discord_user_id: int) -> dict:
    return _post(
        "discord-form",
        {"discord_user_id": discord_user_id},
        timeout=LOAD_TIMEOUT,
    )


def save_answers(discord_user_id: int, answers: dict) -> dict:
    return _post(
        "discord-submit",
        {"discord_user_id": discord_user_id, **answers},
        timeout=15,
    )


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def field_description(question: dict) -> str | None:
    """The line under a field's label: the help text, else the full prompt
    when the label shortened it. Never a repeat of the label."""
    label = (question.get("short") or question.get("prompt") or "").strip()
    for text in (question.get("help"), question.get("prompt")):
        text = (text or "").strip()
        if text and text != label:
            return _clip(text, DESCRIPTION_MAX)
    return None


def modal_title(form: dict) -> str:
    """Names what the form is about, e.g. "About your 3 fleet invites"."""
    count = len(form.get("invites") or [])
    if not count:
        return TITLE
    noun = "fleet invite" if count == 1 else "fleet invites"
    return _clip(f"About your {count} {noun}", LABEL_MAX)


def invite_listing(form: dict) -> str:
    """The pilot's invites as markdown, the same list the DM shows."""
    invites = (form.get("invites") or [])[:LISTING_LIMIT]
    if not invites:
        return ""
    lines = [
        f"- {invite['when']} · {invite['title']} · {invite['answer_label']}"
        for invite in invites
    ]
    extra = len(form.get("invites") or []) - len(invites)
    if extra > 0:
        lines.append(f"and {extra} more")
    heading = form.get("list_heading") or "Your invites"
    return f"**{heading}**\n" + "\n".join(lines)


def panel_text(panel: dict) -> str:
    """A closed, not-invited, or thanks panel as one message."""
    parts = [
        f"**{panel.get('heading')}**" if panel.get("heading") else "",
        panel.get("body") or "",
        panel.get("detail") or "",
    ]
    return "\n".join(part for part in parts if part)


class FeedbackModal(discord.ui.Modal):
    """One dropdown per question, then the comment. Built from the API form."""

    def __init__(self, form: dict):
        super().__init__(title=modal_title(form), timeout=None)
        answers = form.get("answers") or {}
        questions = form.get("questions") or []
        self.selects: dict[str, discord.ui.Select] = {}
        # The questions and the comment take up to all five items. When one
        # is free (no open-invites question), the invite list goes first.
        listing = invite_listing(form)
        if listing and len(questions[: MAX_FIELDS - 1]) + 2 <= MAX_FIELDS:
            self.add_item(discord.ui.TextDisplay(listing))
        has_other = False
        for question in questions[: MAX_FIELDS - 1]:
            select = self._select(question, answers.get(question["key"]))
            self.selects[question["key"]] = select
            if any(c["key"] == "other" for c in question.get("choices", [])):
                has_other = True
            self.add_item(
                discord.ui.Label(
                    text=_clip(
                        question.get("short") or question["prompt"], LABEL_MAX
                    ),
                    description=field_description(question),
                    component=select,
                )
            )
        self.comment = discord.ui.TextInput(
            style=discord.TextStyle.long,
            custom_id="comment",
            required=False,
            max_length=COMMENT_MAX,
            placeholder=_clip(
                form.get("comment_placeholder") or "", DESCRIPTION_MAX
            )
            or None,
            default=_clip(
                answers.get("comment") or answers.get("why_text") or "",
                COMMENT_MAX,
            )
            or None,
        )
        self.add_item(
            discord.ui.Label(
                text=_clip(
                    form.get("comment_heading") or "Comment", LABEL_MAX
                ),
                description=OTHER_HINT if has_other else None,
                component=self.comment,
            )
        )

    @staticmethod
    def _select(question: dict, saved) -> discord.ui.Select:
        multi = question.get("kind") == "multi"
        picked = set(saved if isinstance(saved, list) else [saved or ""])
        options = [
            discord.SelectOption(
                label=_clip(choice["label"], OPTION_MAX),
                value=choice["key"],
                default=choice["key"] in picked,
            )
            for choice in question.get("choices", [])
        ]
        max_values = max(1, int(question.get("max") or 1)) if multi else 1
        return discord.ui.Select(
            custom_id=question["key"],
            placeholder=(
                f"Pick up to {max_values}" if multi and max_values > 1
                else "Pick one"
            ),
            options=options,
            min_values=1,
            max_values=min(max_values, len(options)),
            required=True,
        )

    def answers(self) -> dict:
        answers = {
            "felt": "",
            "sitting_out": "",
            "why": "",
            "why_text": "",
            "keep": "",
            "comment": (self.comment.value or "").strip(),
        }
        for key, select in self.selects.items():
            if select.max_values > 1:
                answers[key] = list(select.values)
            else:
                answers[key] = select.values[0] if select.values else ""
        return answers

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            panel = await asyncio.to_thread(
                save_answers, interaction.user.id, self.answers()
            )
        except FeedbackApiError as exc:
            message = "\n".join(exc.errors)
            await interaction.followup.send(
                f"{message}\n{WEBSITE_URL}", ephemeral=True
            )
            return
        except Exception:
            logger.exception("Saving fleet invite feedback failed")
            await interaction.followup.send(
                f"{SAVE_FAILED}\n{WEBSITE_URL}", ephemeral=True
            )
            return
        await interaction.followup.send(panel_text(panel), ephemeral=True)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        logger.exception("Fleet invite feedback form failed", exc_info=error)
        message = f"{SAVE_FAILED}\n{WEBSITE_URL}"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class AnswerFeedbackButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=INVITE_FEEDBACK_ANSWER_TEMPLATE,
):
    def __init__(self, round_id: int):
        super().__init__(
            discord.ui.Button(
                label="Answer",
                style=discord.ButtonStyle.primary,
                custom_id=custom_id(INVITE_FEEDBACK_ANSWER_PREFIX, round_id),
            )
        )
        self.round_id = round_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["round_id"]))

    async def callback(self, interaction: discord.Interaction):
        # The pilot's own form, not the round in the button: the API finds
        # their latest row, so an old DM still opens the current form.
        try:
            form = await asyncio.wait_for(
                asyncio.to_thread(load_form, interaction.user.id),
                timeout=LOAD_TIMEOUT,
            )
        except FeedbackApiError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("Loading fleet invite feedback form failed")
            await interaction.response.send_message(
                f"{LOAD_FAILED}\n{WEBSITE_URL}", ephemeral=True
            )
            return
        if form.get("state") != "form":
            await interaction.response.send_message(
                panel_text(form), ephemeral=True
            )
            return
        await interaction.response.send_modal(FeedbackModal(form))


def register_fleet_invite_feedback_form(client: discord.Client) -> None:
    client.add_dynamic_items(AnswerFeedbackButton)
