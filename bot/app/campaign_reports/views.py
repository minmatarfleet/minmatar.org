"""/campaign-timer and /campaign-structure: report to a campaign from
its coordination server or a server linked to it.

The commands are global, so they show in every server the bot is in; the
API answers "this server isn't running a campaign" elsewhere and decides
who may report (the campaign's Recon and Coordinators).
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands

from .api import ReportError, ReportRequest, list_campaigns, submit_report

logger = logging.getLogger(__name__)

STRUCTURE_TYPES = [
    ("Astrahus", "astrahus"),
    ("Fortizar", "fortizar"),
    ("Keepstar", "keepstar"),
    ("Raitaru", "raitaru"),
    ("Azbel", "azbel"),
    ("Sotiyo", "sotiyo"),
    ("Athanor", "athanor"),
    ("Tatara", "tatara"),
    ("Ansiblex Jump Gate", "ansiblex_jump_gate"),
    ("Pharolux Cyno Beacon", "pharolux_cyno_beacon"),
    ("Tenebrex Cyno Jammer", "tenebrex_cyno_jammer"),
    ("Metenox Moon Drill", "metenox_moon_drill"),
    ("Orbital Skyhook", "orbital_skyhook"),
    ("Mercenary Den", "mercenary_den"),
    ("Customs Office", "player_owned_customs_office"),
    ("Starbase (POS)", "player_owned_starbase"),
]
TIMER_STATES = [
    ("Armor", "armor"),
    ("Hull", "hull"),
    ("Anchoring", "anchoring"),
    ("Unanchoring", "unanchoring"),
]


def _choices(pairs):
    return [
        app_commands.Choice(name=name, value=value) for name, value in pairs
    ]


class _ReportModal(discord.ui.Modal):
    """Shared submit: post to the API off the event loop, answer privately."""

    kind = ""

    def __init__(self, structure_type: str, campaign: str, **kwargs):
        super().__init__(**kwargs)
        self.structure_type = structure_type
        self.campaign = campaign

    def build_request(self, interaction: discord.Interaction) -> ReportRequest:
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction):
        try:
            request = self.build_request(interaction)
        except ReportError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = await asyncio.to_thread(submit_report, request)
            message = f"{result.message}\n{result.url}"
        except ReportError as exc:
            message = str(exc)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Campaign %s report failed", self.kind)
            message = "Couldn't save that. Try again in a bit."
        await interaction.followup.send(message, ephemeral=True)


class TimerReportModal(_ReportModal, title="Report a timer"):
    kind = "timer"

    paste = discord.ui.TextInput(
        label="Selected item window",
        style=discord.TextStyle.long,
        placeholder="Sosala - WATERMELLON\n0 m\nReinforced until 2026.11.23 19:20:00",
        required=True,
        max_length=1000,
    )
    corporation_name = discord.ui.TextInput(
        label="Owner corporation",
        required=False,
        max_length=255,
    )
    alliance_name = discord.ui.TextInput(
        label="Owner alliance",
        required=False,
        max_length=255,
    )

    def __init__(self, structure_type: str, state: str, campaign: str):
        super().__init__(structure_type, campaign)
        self.state = state

    def build_request(self, interaction: discord.Interaction) -> ReportRequest:
        return ReportRequest(
            guild_id=interaction.guild_id,
            discord_user_id=interaction.user.id,
            campaign=self.campaign,
            kind=self.kind,
            structure_type=self.structure_type,
            timer_state=self.state,
            selected_item_window=self.paste.value,
            corporation_name=self.corporation_name.value or "",
            alliance_name=self.alliance_name.value or "",
        )


class StructureReportModal(_ReportModal, title="Report a structure"):
    kind = "structure"

    paste = discord.ui.TextInput(
        label="Selected item window",
        style=discord.TextStyle.long,
        placeholder="Sosala - WATERMELLON\n12 km",
        required=True,
        max_length=1000,
    )
    corporation_name = discord.ui.TextInput(
        label="Owner corporation",
        required=False,
        max_length=255,
    )
    alliance_name = discord.ui.TextInput(
        label="Owner alliance",
        required=False,
        max_length=255,
    )
    reinforce_hour = discord.ui.TextInput(
        label="Reinforcement hour (EVE time, 0-23)",
        required=False,
        max_length=2,
    )

    def build_request(self, interaction: discord.Interaction) -> ReportRequest:
        hour = (self.reinforce_hour.value or "").strip()
        if hour and not hour.isdigit():
            raise ReportError("The reinforcement hour is a number, 0 to 23.")
        return ReportRequest(
            guild_id=interaction.guild_id,
            discord_user_id=interaction.user.id,
            campaign=self.campaign,
            kind=self.kind,
            structure_type=self.structure_type,
            selected_item_window=self.paste.value,
            corporation_name=self.corporation_name.value or "",
            alliance_name=self.alliance_name.value or "",
            reinforce_hour=int(hour) if hour else None,
        )


async def campaign_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if interaction.guild_id is None:
        return []
    try:
        campaigns = await asyncio.to_thread(
            list_campaigns, interaction.guild_id, interaction.user.id
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning("Could not list campaigns for autocomplete")
        return []
    wanted = current.lower()
    return [
        app_commands.Choice(name=campaign.name[:100], value=campaign.slug)
        for campaign in campaigns
        if wanted in campaign.name.lower() or wanted in campaign.slug
    ][:25]


def register_campaign_report_commands(tree: app_commands.CommandTree):
    """Global commands: campaigns are run from other servers."""

    @tree.command(
        name="campaign-timer",
        description="Report a structure timer to this server's campaign",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        structure="What the structure is",
        state="The timer it is on",
        campaign="Only when this server runs more than one campaign",
    )
    @app_commands.choices(
        structure=_choices(STRUCTURE_TYPES), state=_choices(TIMER_STATES)
    )
    @app_commands.autocomplete(campaign=campaign_autocomplete)
    async def campaign_timer(
        interaction: discord.Interaction,
        structure: app_commands.Choice[str],
        state: app_commands.Choice[str],
        campaign: str = "",
    ):
        await interaction.response.send_modal(
            TimerReportModal(structure.value, state.value, campaign)
        )

    @tree.command(
        name="campaign-structure",
        description="Report a structure to this server's campaign",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        structure="What the structure is",
        campaign="Only when this server runs more than one campaign",
    )
    @app_commands.choices(structure=_choices(STRUCTURE_TYPES))
    @app_commands.autocomplete(campaign=campaign_autocomplete)
    async def campaign_structure(
        interaction: discord.Interaction,
        structure: app_commands.Choice[str],
        campaign: str = "",
    ):
        await interaction.response.send_modal(
            StructureReportModal(structure.value, campaign)
        )
