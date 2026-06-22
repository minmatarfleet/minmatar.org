import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from pydantic import BaseModel

from authentication import AuthBearer
from discord.client import DiscordClient
from discord.models import DiscordUser
from help_tickets.helpers.panel import build_help_ticket_panel_config
from help_tickets.models import (
    HelpRequestCategory,
    HelpTicket,
    HelpTicketPanel,
)

router = Router(tags=["Help tickets"])
logger = logging.getLogger(__name__)
discord = DiscordClient()


class HelpTicketPanelCategorySchema(BaseModel):
    id: int
    code: str
    title: str
    description: str
    section: str
    mention_discord_ids: list[int]


class HelpTicketPanelConfigSchema(BaseModel):
    hash: str
    embed_title: str
    embed_description: str
    categories: list[HelpTicketPanelCategorySchema]


class HelpTicketPanelStateSchema(BaseModel):
    channel_id: int
    message_id: int | None
    content_hash: str


class HelpTicketPanelStateUpdateSchema(BaseModel):
    channel_id: int
    message_id: int
    content_hash: str


class CreateHelpTicketRequest(BaseModel):
    category_id: int
    opener_discord_id: int
    thread_id: int
    thread_name: str
    body: str


class HelpTicketResponse(BaseModel):
    id: int
    status: str
    thread_id: int
    opener_discord_id: int


class OpenHelpTicketSchema(BaseModel):
    id: int
    thread_id: int


class OpenHelpTicketsResponse(BaseModel):
    tickets: list[OpenHelpTicketSchema]


class CloseHelpTicketRequest(BaseModel):
    closed_by_discord_id: int
    close_reason: str = ""


@router.get(
    "/panel-config",
    response=HelpTicketPanelConfigSchema,
    auth=AuthBearer(),
)
def get_help_ticket_panel_config(request):
    return build_help_ticket_panel_config()


@router.get(
    "/panel-state",
    response=HelpTicketPanelStateSchema,
    auth=AuthBearer(),
)
def get_help_ticket_panel_state(request):
    panel = HelpTicketPanel.get_solo()
    return {
        "channel_id": panel.channel_id,
        "message_id": panel.message_id,
        "content_hash": panel.content_hash,
    }


@router.put(
    "/panel-state",
    response=HelpTicketPanelStateSchema,
    auth=AuthBearer(),
)
def update_help_ticket_panel_state(
    request, payload: HelpTicketPanelStateUpdateSchema
):
    panel = HelpTicketPanel.get_solo()
    panel.channel_id = payload.channel_id
    panel.message_id = payload.message_id
    panel.content_hash = payload.content_hash
    panel.save(
        update_fields=["channel_id", "message_id", "content_hash"],
    )
    return {
        "channel_id": panel.channel_id,
        "message_id": panel.message_id,
        "content_hash": panel.content_hash,
    }


def _resolve_user(discord_id: int):
    discord_user = DiscordUser.objects.filter(id=discord_id).first()
    if discord_user is None:
        return None
    return discord_user.user


@router.post(
    "/",
    response=HelpTicketResponse,
    auth=AuthBearer(),
)
def create_help_ticket(request, payload: CreateHelpTicketRequest):
    category = get_object_or_404(
        HelpRequestCategory,
        pk=payload.category_id,
        is_active=True,
    )
    ticket = HelpTicket.objects.create(
        category=category,
        opener_discord_id=payload.opener_discord_id,
        opener=_resolve_user(payload.opener_discord_id),
        thread_id=payload.thread_id,
        thread_name=payload.thread_name,
        body=payload.body,
        status=HelpTicket.STATUS_OPEN,
    )
    return {
        "id": ticket.id,
        "status": ticket.status,
        "thread_id": ticket.thread_id,
        "opener_discord_id": ticket.opener_discord_id,
    }


@router.get(
    "/open",
    response=OpenHelpTicketsResponse,
    auth=AuthBearer(),
)
def list_open_help_tickets(request):
    tickets = HelpTicket.objects.filter(
        status=HelpTicket.STATUS_OPEN
    ).order_by("opened_at")
    return {
        "tickets": [
            {"id": ticket.id, "thread_id": ticket.thread_id}
            for ticket in tickets
        ],
    }


@router.get(
    "/{ticket_id}/",
    response=HelpTicketResponse,
    auth=AuthBearer(),
)
def get_help_ticket(request, ticket_id: int):
    ticket = get_object_or_404(HelpTicket, pk=ticket_id)
    return {
        "id": ticket.id,
        "status": ticket.status,
        "thread_id": ticket.thread_id,
        "opener_discord_id": ticket.opener_discord_id,
    }


@router.patch(
    "/{ticket_id}/close/",
    response=HelpTicketResponse,
    auth=AuthBearer(),
)
def close_help_ticket(
    request, ticket_id: int, payload: CloseHelpTicketRequest
):
    ticket = get_object_or_404(HelpTicket, pk=ticket_id)
    if ticket.status == HelpTicket.STATUS_CLOSED:
        raise HttpError(400, "Ticket is already closed.")

    try:
        discord.close_thread(channel_id=ticket.thread_id)
    except Exception as exc:
        logger.exception(
            "Failed to close Discord thread for ticket %s", ticket_id
        )
        raise HttpError(502, "Could not close the Discord thread.") from exc

    ticket.status = HelpTicket.STATUS_CLOSED
    ticket.closed_at = timezone.now()
    ticket.closed_by_discord_id = payload.closed_by_discord_id
    ticket.closed_by = _resolve_user(payload.closed_by_discord_id)
    ticket.close_reason = payload.close_reason
    ticket.save(
        update_fields=[
            "status",
            "closed_at",
            "closed_by_discord_id",
            "closed_by",
            "close_reason",
        ],
    )
    return {
        "id": ticket.id,
        "status": ticket.status,
        "thread_id": ticket.thread_id,
        "opener_discord_id": ticket.opener_discord_id,
    }
