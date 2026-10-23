"""The Invites tab: waves, answers, re-ping and the wave picker."""

from __future__ import annotations

from collections import defaultdict
from typing import List

from django.db.models import Q

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)
from eveonline.models import EveCharacter, EveCorporation
from fleets.endpoints.private.schemas import (
    FleetInvitesResponse,
    InviteCandidate,
    InvitePilot,
    InviteTotals,
    InviteWave,
    RepingResponse,
    ShipTargetProgress,
    WavePreviewResponse,
    WaveRequest,
    WaveSentResponse,
)
from fleets.helpers.private_fleet_discord import thread_url
from fleets.helpers.private_fleets import (
    REPING_COOLDOWN,
    PrivateFleetError,
    invite_totals,
    reping_no_answers,
    send_wave,
    sending_wave,
    target_progress,
    wave_preview,
)
from fleets.helpers.private_visibility import sees_every_private_fleet
from fleets.models import (
    EveFleet,
    EveFleetInvite,
    EveFleetInviteWave,
    EveFleetShipVolunteer,
)

_ERRORS = {400: ErrorResponse, 403: None, 404: None, 409: ErrorResponse}


def can_manage_invites(user, fleet: EveFleet) -> bool:
    """The fleet's creator, Strategic FCs and superusers."""
    if not getattr(user, "is_authenticated", False):
        return False
    return fleet.created_by_id == user.pk or sees_every_private_fleet(user)


def _private_fleet(request, fleet_id: int):
    """The fleet if the caller may manage its invites, else an error."""
    fleet = (
        EveFleet.objects.select_related("audience", "location", "created_by")
        .filter(id=fleet_id, invite_only=True)
        .first()
    )
    if fleet is None:
        return 404, None
    if not can_manage_invites(request.user, fleet):
        # Don't confirm a private fleet exists to someone who can't see it.
        return 404, None
    return fleet


def _wave_labels(waves) -> dict[int, list[str]]:
    # pylint: disable=import-outside-toplevel
    from tribes.models import TribeGroup

    group_ids = {i for w in waves for i in w.tribe_group_ids or []}
    corp_ids = {i for w in waves for i in w.corporation_ids or []}
    groups = {
        g.id: f"{g.tribe.name} · {g.name}"
        for g in TribeGroup.objects.filter(id__in=group_ids).select_related(
            "tribe"
        )
    }
    corps = dict(
        EveCorporation.objects.filter(corporation_id__in=corp_ids).values_list(
            "corporation_id", "name"
        )
    )
    labels = {}
    for wave in waves:
        out = [groups[i] for i in wave.tribe_group_ids or [] if i in groups]
        out += [
            corps.get(i) or f"Corp {i}" for i in wave.corporation_ids or []
        ]
        pilots = len(wave.user_ids or [])
        if pilots:
            out.append("1 pilot" if pilots == 1 else f"{pilots} pilots")
        labels[wave.id] = out
    return labels


def _ships_by_user(fleet, user_ids) -> dict[int, list[str]]:
    owners = dict(
        EveCharacter.objects.filter(user_id__in=user_ids).values_list(
            "character_id", "user_id"
        )
    )
    ships: dict[int, list[str]] = defaultdict(list)
    for volunteer in EveFleetShipVolunteer.objects.filter(
        eve_fleet=fleet, character_id__in=list(owners)
    ).select_related("fitting", "fleet_fitting"):
        ship = volunteer.ship_name
        if volunteer.fitting_id:
            ship = volunteer.fitting.name
        elif volunteer.fleet_fitting_id:
            ship = volunteer.fleet_fitting.name
        ships[owners[volunteer.character_id]].append(
            f"{ship} ({volunteer.character_name})"
        )
    return ships


def get_fleet_invites(request, fleet_id: int):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    leak_trace = sees_every_private_fleet(request.user)
    waves = list(
        EveFleetInviteWave.objects.filter(eve_fleet=fleet).select_related(
            "sent_by"
        )
    )
    invites = list(
        EveFleetInvite.objects.filter(eve_fleet=fleet).select_related("wave")
    )
    user_ids = [i.user_id for i in invites]
    mains = primary_characters_for_users(user_ids)
    corps = dict(
        EveCorporation.objects.filter(
            corporation_id__in={
                c.corporation_id for c in mains.values() if c.corporation_id
            }
        ).values_list("corporation_id", "name")
    )
    ships = _ships_by_user(fleet, user_ids)
    labels = _wave_labels(waves)
    by_wave: dict[int, list] = defaultdict(list)
    for invite in invites:
        by_wave[invite.wave_id].append(invite)

    pilots = []
    for invite in invites:
        main = mains.get(invite.user_id)
        pilots.append(
            InvitePilot(
                invite_id=invite.id,
                user_id=invite.user_id,
                character_id=main.character_id if main else None,
                character_name=(
                    main.character_name if main else f"User {invite.user_id}"
                ),
                corporation_name=(
                    corps.get(main.corporation_id) if main else None
                ),
                wave=invite.wave.number,
                answer=invite.answer,
                ships=ships.get(invite.user_id, []),
                answered_at=invite.answered_at,
                first_viewed_at=(
                    invite.first_viewed_at if leak_trace else None
                ),
                sent_at=invite.sent_at,
                dm_delivered=invite.dm_delivered,
            )
        )
    wave_rows = []
    for wave in waves:
        members = by_wave.get(wave.id, [])
        wave_rows.append(
            InviteWave(
                number=wave.number,
                sent_by=wave.sent_by.username if wave.sent_by else None,
                created_at=wave.created_at,
                finished_at=wave.finished_at,
                note=wave.note,
                labels=labels.get(wave.id, []),
                invited=len(members),
                sent=sum(1 for i in members if i.dm_delivered is not None),
                answered_in=sum(1 for i in members if i.answer == "in"),
                answered_out=sum(1 for i in members if i.answer == "out"),
                pending=sum(1 for i in members if i.answer == "pending"),
            )
        )
    totals = invite_totals(fleet)
    reminded = [i.reminded_at for i in invites if i.reminded_at]
    return FleetInvitesResponse(
        fleet_id=fleet.id,
        totals=InviteTotals(
            invited=totals["invited"],
            answered_in=totals["in"],
            characters_in=totals["characters_in"],
            answered_out=totals["out"],
            pending=totals["pending"],
        ),
        waves=wave_rows,
        invites=pilots,
        targets=[ShipTargetProgress(**row) for row in target_progress(fleet)],
        sending=sending_wave(fleet) is not None,
        reping_available_at=(
            max(reminded) + REPING_COOLDOWN if reminded else None
        ),
        can_see_leak_trace=leak_trace,
        thread_url=thread_url(fleet),
    )


def _preview_response(preview: dict) -> WavePreviewResponse:
    return WavePreviewResponse(
        picked=preview["picked"],
        already_invited=preview["already_invited"],
        new=len(preview["new_user_ids"]),
        will_dm=preview["will_dm"],
        no_discord=len(preview["no_discord_user_ids"]),
        helps=preview["helps"],
    )


def post_wave_preview(request, fleet_id: int, payload: WaveRequest):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    return _preview_response(
        wave_preview(
            fleet,
            tribe_group_ids=payload.tribe_group_ids,
            corporation_ids=payload.corporation_ids,
            user_ids=payload.user_ids,
        )
    )


def post_wave(request, fleet_id: int, payload: WaveRequest):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    try:
        wave = send_wave(
            fleet,
            sent_by=request.user,
            tribe_group_ids=payload.tribe_group_ids,
            corporation_ids=payload.corporation_ids,
            user_ids=payload.user_ids,
            note=payload.note,
        )
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    invites = EveFleetInvite.objects.filter(wave=wave)
    return 201, WaveSentResponse(
        number=wave.number,
        invited=invites.count(),
        will_dm=invites.filter(dm_delivered__isnull=True).count(),
    )


def post_reping(request, fleet_id: int):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    try:
        pilots = reping_no_answers(fleet)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 202, RepingResponse(pilots=pilots)


def get_invite_candidates(request, fleet_id: int, q: str = ""):
    """Tribe groups, corporations and pilots matching ``q``, for the wave
    picker."""
    # pylint: disable=import-outside-toplevel
    from tribes.models import TribeGroup

    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    q = (q or "").strip()
    if len(q) < 2:
        return []
    out: List[InviteCandidate] = []
    for group in (
        TribeGroup.objects.filter(is_active=True)
        .filter(Q(name__icontains=q) | Q(tribe__name__icontains=q))
        .select_related("tribe")[:8]
    ):
        out.append(
            InviteCandidate(
                kind="tribe_group",
                id=group.id,
                name=f"{group.tribe.name} · {group.name}",
                detail="Tribe group",
            )
        )
    for corp in EveCorporation.objects.filter(
        Q(name__icontains=q) | Q(ticker__iexact=q)
    ).order_by("name")[:6]:
        out.append(
            InviteCandidate(
                kind="corporation",
                id=corp.corporation_id,
                name=corp.name,
                detail=f"[{corp.ticker}]" if corp.ticker else "Corporation",
            )
        )
    seen = set()
    characters = list(
        EveCharacter.objects.filter(
            character_name__icontains=q, user__isnull=False
        )
        .select_related("user")
        .order_by("character_name")[:10]
    )
    corp_names = dict(
        EveCorporation.objects.filter(
            corporation_id__in={c.corporation_id for c in characters}
        ).values_list("corporation_id", "name")
    )
    for character in characters:
        if character.user_id in seen:
            continue
        seen.add(character.user_id)
        out.append(
            InviteCandidate(
                kind="pilot",
                id=character.user_id,
                name=character.character_name,
                detail=corp_names.get(character.corporation_id, ""),
            )
        )
    return out


ROUTES = (
    (
        "get",
        "/{fleet_id}/invites",
        {
            "auth": AuthBearer(),
            "response": {200: FleetInvitesResponse, 404: None},
            "description": (
                "A private fleet's invite waves and answers, for its FC and "
                "Strategic FCs. first_viewed_at (the leak trace) is null "
                "unless the caller is a Strategic FC."
            ),
        },
        get_fleet_invites,
    ),
    (
        "post",
        "/{fleet_id}/invites/preview",
        {
            "auth": AuthBearer(),
            "response": {200: WavePreviewResponse, **_ERRORS},
            "description": "Who a wave with these picks would reach.",
        },
        post_wave_preview,
    ),
    (
        "post",
        "/{fleet_id}/invites/waves",
        {
            "auth": AuthBearer(),
            "response": {201: WaveSentResponse, **_ERRORS},
            "description": (
                "Invite the new players in these picks. The DMs go out from "
                "a task at about one a second; one wave sends at a time."
            ),
        },
        post_wave,
    ),
    (
        "post",
        "/{fleet_id}/invites/reping",
        {
            "auth": AuthBearer(),
            "response": {
                202: RepingResponse,
                429: ErrorResponse,
                **_ERRORS,
            },
            "description": (
                "DM everyone who hasn't answered once more. At most once "
                "every 15 minutes per fleet."
            ),
        },
        post_reping,
    ),
    (
        "get",
        "/{fleet_id}/invites/candidates",
        {
            "auth": AuthBearer(),
            "response": {200: List[InviteCandidate], 404: None},
            "description": "Tribe groups, corporations and pilots to invite.",
        },
        get_invite_candidates,
    ),
)
