from pydantic import BaseModel

from app.settings import settings

HELP_TICKETS_BASE_URL = f"{settings.API_URL}/help-tickets"
PANEL_CONFIG_URL = f"{HELP_TICKETS_BASE_URL}/panel-config"
PANEL_STATE_URL = f"{HELP_TICKETS_BASE_URL}/panel-state"
OPEN_TICKETS_URL = f"{HELP_TICKETS_BASE_URL}/open"


class HelpTicketPanelCategory(BaseModel):
    id: int
    code: str
    title: str
    description: str
    section: str
    mention_discord_ids: list[int] = []


class HelpTicketPanelConfig(BaseModel):
    hash: str
    embed_title: str
    embed_description: str
    categories: list[HelpTicketPanelCategory]


class HelpTicketPanelState(BaseModel):
    channel_id: int
    message_id: int | None = None
    content_hash: str = ""


class HelpTicketPanelStateUpdate(BaseModel):
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


class CloseHelpTicketRequest(BaseModel):
    closed_by_discord_id: int
    close_reason: str = ""


class OpenHelpTicket(BaseModel):
    id: int
    thread_id: int


class OpenHelpTicketsResponse(BaseModel):
    tickets: list[OpenHelpTicket]
