"""Sign up for a fleet invite from the one-time link the bot hands out when
a pilot presses I'm available (docs/fleets/invite-rsvp.md).

The bot route needs the bot's token. The /rsvp/ routes need no login: the
signed token in the path is the only key, and it can only answer that one
invite.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.private.answers import _discord_invite
from fleets.endpoints.private.schemas import DiscordSitOutRequest
from fleets.helpers.invite_rsvp import (
    OPEN_MAX_AGE,
    SUBMIT_MAX_AGE,
    Pick,
    RsvpError,
    build_form,
    invite_for_token,
    link_for,
    mint_token,
    not_available,
    submit,
)
from fleets.helpers.private_fleet_discord import fleet_title
from fleets.helpers.private_fleets import target_progress
from fleets.models import EveFleetShipVolunteer


class RsvpLinkResponse(BaseModel):
    url: str
    expires_minutes: int


class RsvpFitResponse(BaseModel):
    key: str
    name: str
    ship_id: int
    ship_name: str
    role: str
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None


class RsvpCharacterResponse(BaseModel):
    character_id: int
    name: str
    # The EVE account the site thinks this character is on (inferred or
    # set by the pilot); two picks on one account can't both fly.
    account: Optional[int] = None
    fits: List[RsvpFitResponse]
    suggested_key: str = ""
    suggested_fleets: int = 0
    picked: bool = False
    picked_key: str = ""


class RsvpFleetResponse(BaseModel):
    id: int
    title: str
    type: str
    type_label: str
    invite_only: bool
    start_time: datetime
    formup: Optional[str] = None
    doctrine: Optional[str] = None
    fc_name: str
    fc_character_id: Optional[int] = None
    wanted: List[str] = []


class RsvpFormResponse(BaseModel):
    fleet: RsvpFleetResponse
    pilot_name: str
    pilot_character_id: Optional[int] = None
    characters: List[RsvpCharacterResponse]
    hidden_count: int
    any_ship: bool
    answer: str
    confidence: str
    # Send the answer with this, not the link's token: it lasts an hour.
    submit_token: str


class RsvpPickRequest(BaseModel):
    character_id: int
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None


class RsvpSubmitRequest(BaseModel):
    picks: List[RsvpPickRequest] = []
    confidence: str = Field(default="high")


class RsvpShipResponse(BaseModel):
    character_id: int
    character_name: str
    ship_name: str
    ship_id: Optional[int] = None


class RsvpResultResponse(BaseModel):
    fleet: RsvpFleetResponse
    answer: str
    confidence: str
    ships: List[RsvpShipResponse]


def _error(exc: RsvpError):
    return exc.status_code, ErrorResponse(detail=str(exc))


def _fleet(fleet) -> RsvpFleetResponse:
    fc = fleet.fleet_commander
    return RsvpFleetResponse(
        id=fleet.id,
        title=fleet_title(fleet),
        type=fleet.type,
        type_label=fleet.get_type_display(),
        invite_only=fleet.invite_only,
        start_time=fleet.start_time,
        formup=(
            fleet.formup_location.location_name
            if fleet.formup_location
            else None
        ),
        doctrine=fleet.doctrine.name if fleet.doctrine_id else None,
        fc_name=(
            fc.character_name
            if fc
            else (fleet.created_by.username if fleet.created_by else "The FC")
        ),
        fc_character_id=fc.character_id if fc else None,
        wanted=[
            f"{row['name']} {row['short']}"
            for row in target_progress(fleet)
            if row["short"] > 0
        ],
    )


def post_invite_discord_available(
    request, invite_id: int, payload: DiscordSitOutRequest
):
    """The bot, on behalf of the Discord user who pressed I'm available:
    a sign-up link only that pilot gets."""
    invite = _discord_invite(request, invite_id, payload.discord_user_id)
    if isinstance(invite, tuple):
        return invite
    try:
        url = link_for(invite)
    except RsvpError as exc:
        return _error(exc)
    return 200, RsvpLinkResponse(url=url, expires_minutes=OPEN_MAX_AGE // 60)


def get_rsvp(request, token: str):
    # pylint: disable=import-outside-toplevel
    from eveonline.helpers.characters import user_primary_character

    try:
        invite = invite_for_token(token, max_age=OPEN_MAX_AGE)
        form = build_form(invite)
    except RsvpError as exc:
        return _error(exc)
    primary = user_primary_character(invite.user)
    return 200, RsvpFormResponse(
        fleet=_fleet(invite.eve_fleet),
        pilot_name=(
            primary.character_name if primary else invite.user.username
        ),
        pilot_character_id=primary.character_id if primary else None,
        characters=[
            RsvpCharacterResponse(
                character_id=row.character_id,
                name=row.name,
                account=row.account,
                fits=[RsvpFitResponse(**fit.__dict__) for fit in row.fits],
                suggested_key=row.suggested_key,
                suggested_fleets=row.suggested_fleets,
                picked=row.picked,
                picked_key=row.picked_key,
            )
            for row in form.characters
        ],
        hidden_count=form.hidden_count,
        any_ship=form.any_ship,
        answer=invite.answer,
        confidence=invite.confidence,
        submit_token=mint_token(invite),
    )


def _result(invite) -> RsvpResultResponse:
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter

    character_ids = EveCharacter.objects.filter(
        user_id=invite.user_id
    ).values_list("character_id", flat=True)
    ships = []
    for volunteer in EveFleetShipVolunteer.objects.filter(
        eve_fleet_id=invite.eve_fleet_id,
        character_id__in=list(character_ids),
    ).select_related("fitting", "fleet_fitting"):
        if volunteer.fitting_id:
            name, ship_id = volunteer.fitting.name, volunteer.fitting.ship_id
        elif volunteer.fleet_fitting_id:
            name = volunteer.fleet_fitting.name
            ship_id = volunteer.fleet_fitting.ship_id
        else:
            name, ship_id = volunteer.ship_name, volunteer.ship_type_id
        ships.append(
            RsvpShipResponse(
                character_id=volunteer.character_id,
                character_name=volunteer.character_name,
                ship_name=name,
                ship_id=ship_id,
            )
        )
    return RsvpResultResponse(
        fleet=_fleet(invite.eve_fleet),
        answer=invite.answer,
        confidence=invite.confidence,
        ships=ships,
    )


def post_rsvp(request, token: str, payload: RsvpSubmitRequest):
    try:
        invite = invite_for_token(token, max_age=SUBMIT_MAX_AGE)
        invite = submit(
            invite,
            [Pick(**pick.model_dump()) for pick in payload.picks],
            payload.confidence,
        )
    except RsvpError as exc:
        return _error(exc)
    return 200, _result(invite)


def post_rsvp_not_available(request, token: str):
    try:
        invite = invite_for_token(token, max_age=SUBMIT_MAX_AGE)
        invite = not_available(invite)
    except RsvpError as exc:
        return _error(exc)
    return 200, _result(invite)


_ERRORS = {400: ErrorResponse, 403: ErrorResponse, 410: ErrorResponse}

ROUTES = (
    (
        "post",
        "/invites/{invite_id}/discord-available",
        {
            "auth": AuthBearer(),
            "response": {200: RsvpLinkResponse, 404: ErrorResponse, **_ERRORS},
            "description": (
                "I'm available from the invite DM's button (bot): a sign-up "
                "link for the pilot who pressed it, valid for 10 minutes."
            ),
        },
        post_invite_discord_available,
    ),
    (
        "get",
        "/rsvp/{token}",
        {
            "response": {200: RsvpFormResponse, **_ERRORS},
            "description": (
                "The sign-up form behind a one-time link: the fleet, the "
                "pilot's characters that can fly it with the fits each can "
                "fly, and a submit_token for sending the answer. No login; "
                "the token is the key."
            ),
        },
        get_rsvp,
    ),
    (
        "post",
        "/rsvp/{token}",
        {
            "response": {200: RsvpResultResponse, **_ERRORS},
            "description": (
                "Sign up through a one-time link (use submit_token): the "
                "ships each character brings, and how sure the pilot is "
                "(high, medium: might be 10-15 minutes late, low: might not "
                "make it and isn't counted). No picks signs up with no ship "
                "yet."
            ),
        },
        post_rsvp,
    ),
    (
        "post",
        "/rsvp/{token}/not-available",
        {
            "response": {200: RsvpResultResponse, **_ERRORS},
            "description": (
                "I'm not available, through a one-time link (use "
                "submit_token). Only skips this fleet."
            ),
        },
        post_rsvp_not_available,
    ),
)
