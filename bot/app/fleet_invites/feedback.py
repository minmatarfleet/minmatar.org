"""Discord command to preview, remind, or close fleet invite feedback."""

from __future__ import annotations

import asyncio
import logging

import discord
import requests
from discord import app_commands
from pydantic import BaseModel

from app.settings import settings

logger = logging.getLogger(__name__)

FLEETS_BASE_URL = f"{settings.API_URL}/fleets"
AUTH_HEADERS = {
    "Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}",  # pragma: allowlist secret
}


class FeedbackError(Exception):
    pass


class CommandBody(BaseModel):
    discord_user_id: int
    action: str
    confirm: bool = False


def send_feedback(discord_user_id: int, action: str, confirm: bool) -> str:
    response = requests.post(
        f"{FLEETS_BASE_URL}/invite-feedback/command",
        headers=AUTH_HEADERS,
        json=CommandBody(
            discord_user_id=discord_user_id,
            action=action,
            confirm=confirm,
        ).model_dump(),
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        raise FeedbackError(str(payload.get("detail") or "Request failed"))
    return str(payload.get("message") or "Done.")


async def handle_fleet_invite_feedback(
    interaction: discord.Interaction, action: str, confirm: bool
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        message = await asyncio.to_thread(
            send_feedback, interaction.user.id, action, confirm
        )
    except FeedbackError as exc:
        message = str(exc)
    except Exception:
        logger.exception("Fleet invite feedback command failed")
        message = "Couldn't do that. Try again in a bit."
    await interaction.followup.send(message, ephemeral=True)


def register_fleet_invite_feedback(tree: app_commands.CommandTree, guilds):
    @tree.command(
        guilds=guilds,
        name="fleet-invite-feedback",
        description=(
            "Preview, remind, or close the fleet invite feedback form"
        ),
    )
    @app_commands.describe(
        action="Preview who would get it, remind, or close it",
        confirm="Required to remind or close",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Preview", value="preview"),
            app_commands.Choice(name="Remind", value="remind"),
            app_commands.Choice(name="Close", value="close"),
        ]
    )
    async def fleet_invite_feedback(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        confirm: bool = False,
    ):
        await handle_fleet_invite_feedback(interaction, action.value, confirm)
