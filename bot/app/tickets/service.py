import logging
import re

import discord
import requests

from app.settings import settings

from .api import (
    HELP_TICKETS_BASE_URL,
    OPEN_TICKETS_URL,
    PANEL_CONFIG_URL,
    PANEL_STATE_URL,
    CloseHelpTicketRequest,
    CreateHelpTicketRequest,
    HelpTicketPanelConfig,
    HelpTicketPanelState,
    HelpTicketPanelStateUpdate,
    HelpTicketResponse,
    OpenHelpTicketsResponse,
)

logger = logging.getLogger(__name__)

AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


def _request(method: str, url: str, **kwargs):
    response = requests.request(
        method,
        url,
        headers=AUTH_HEADERS,
        timeout=10,
        **kwargs,
    )
    response.raise_for_status()
    return response


def fetch_panel_config() -> HelpTicketPanelConfig:
    response = _request("GET", PANEL_CONFIG_URL)
    return HelpTicketPanelConfig.model_validate(response.json())


def fetch_panel_state() -> HelpTicketPanelState:
    response = _request("GET", PANEL_STATE_URL)
    return HelpTicketPanelState.model_validate(response.json())


def update_panel_state(payload: HelpTicketPanelStateUpdate) -> HelpTicketPanelState:
    response = _request(
        "PUT",
        PANEL_STATE_URL,
        json=payload.model_dump(),
    )
    return HelpTicketPanelState.model_validate(response.json())


def create_help_ticket(payload: CreateHelpTicketRequest) -> HelpTicketResponse:
    response = _request(
        "POST",
        f"{HELP_TICKETS_BASE_URL}/",
        json=payload.model_dump(),
    )
    return HelpTicketResponse.model_validate(response.json())


def close_help_ticket(
    ticket_id: int, payload: CloseHelpTicketRequest
) -> HelpTicketResponse:
    response = _request(
        "PATCH",
        f"{HELP_TICKETS_BASE_URL}/{ticket_id}/close/",
        json=payload.model_dump(),
    )
    return HelpTicketResponse.model_validate(response.json())


def fetch_help_ticket(ticket_id: int) -> HelpTicketResponse:
    response = _request("GET", f"{HELP_TICKETS_BASE_URL}/{ticket_id}/")
    return HelpTicketResponse.model_validate(response.json())


def fetch_open_help_tickets() -> OpenHelpTicketsResponse:
    response = _request("GET", OPEN_TICKETS_URL)
    return OpenHelpTicketsResponse.model_validate(response.json())


def sanitize_thread_name(group_code: str, username: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", group_code.lower())
    user_slug = re.sub(r"[^a-z0-9-]", "-", username.lower())
    name = f"{slug}-{user_slug}".strip("-")
    name = re.sub(r"-+", "-", name)
    return name[:100] or "help-ticket"


def member_can_close_ticket(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    moderator_role_id = settings.DISCORD_MODERATOR_ROLE_ID
    if not moderator_role_id:
        return False
    return any(role.id == int(moderator_role_id) for role in member.roles)
