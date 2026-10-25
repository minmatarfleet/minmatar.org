"""The Invites tab on any fleet: invited pilots, answers, re-ping, the
pickers and sending invites. See docs/fleets/private-fleets.md."""

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
    CappedPilot,
    FleetInvitesResponse,
    InviteCandidate,
    InvitePilot,
    InviteTotals,
    InviteWave,
    OnboardingCount,
    PickCount,
    RepingResponse,
    ResolveNamesRequest,
    ResolveNamesResponse,
    ResolvedPilot,
    ShipTargetProgress,
    TimezoneCount,
    WavePreviewResponse,
    WaveRequest,
    WaveSentResponse,
)
from fleets.helpers.private_fleet_discord import thread_url
from fleets.helpers.private_fleets import (
    REPING_COOLDOWN,
    PrivateFleetError,
    invite_totals,
    is_capped_fleet,
    onboarding_counts,
    opted_out_user_ids,
    reping_no_answers,
    resolve_invite_names,
    send_wave,
    sending_wave,
    target_progress,
    wave_preview,
    weekly_invites,
)
from fleets.helpers.private_visibility import sees_every_private_fleet
from fleets.models import (
    EveFleet,
    EveFleetInvite,
    EveFleetInviteWave,
    EveFleetShipVolunteer,
)
from timezones.fleet_time import (
    ANY,
    clean_codes,
    fleet_timezones,
    in_timezones,
)
from timezones.services import brackets_for, timezone_tags_for

_ERRORS = {400: ErrorResponse, 403: None, 404: None, 409: ErrorResponse}


def can_manage_invites(user, fleet: EveFleet) -> bool:
    """The fleet's FC (its creator) and superusers; on a private fleet,
    every Strategic FC too."""
    if not getattr(user, "is_authenticated", False):
        return False
    if fleet.created_by_id == user.pk or user.is_superuser:
        return True
    return fleet.invite_only and sees_every_private_fleet(user)


def can_reping(user, fleet: EveFleet) -> bool:
    """Re-ping is for private fleets, and only Strategic FCs send it."""
    return fleet.invite_only and sees_every_private_fleet(user)


def can_choose_timezones(user, fleet: EveFleet) -> bool:
    """Strategic FCs on a strategic or private fleet invite from any
    timezone; everyone else invites only the fleet's."""
    return (
        fleet.type == "strategic" or fleet.invite_only
    ) and sees_every_private_fleet(user)


def chosen_timezones(user, fleet: EveFleet, requested) -> list[str] | None:
    """The brackets bulk picks are limited to; None for any.

    The fleet's own brackets by default. Others may untick some of them,
    but never all, and can't add others; a caller who can choose may send
    any brackets, or "any".
    """
    own, _ = fleet_timezones(fleet.start_time)
    if requested is None:
        return own
    if can_choose_timezones(user, fleet):
        if ANY in requested:
            return None
        return clean_codes(requested) or own
    return [code for code in clean_codes(requested) if code in own] or own


def _request_timezones(raw: str) -> list[str] | None:
    """A comma-separated query parameter; blank means the fleet's own."""
    codes = [code.strip() for code in (raw or "").split(",") if code.strip()]
    return codes or None


def _private_fleet(request, fleet_id: int):
    """The fleet if the caller may manage its invites, else an error."""
    fleet = (
        EveFleet.objects.select_related("audience", "location", "created_by")
        .filter(id=fleet_id)
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


def _ships_by_user(fleet, user_ids, mains) -> dict[int, list[str]]:
    """Each player's signed-up hulls. A hull flown by an alt names the alt."""
    main_ids = {main.character_id for main in mains.values()}
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
        if volunteer.character_id not in main_ids:
            ship = f"{ship} ({volunteer.character_name})"
        ships[owners[volunteer.character_id]].append(ship)
    return ships


def get_fleet_invites(request, fleet_id: int):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    leak_trace = fleet.invite_only and sees_every_private_fleet(request.user)
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
    ships = _ships_by_user(fleet, user_ids, mains)
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
                source_kind=invite.source_kind,
                source_name=invite.source_name,
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
    own_timezones, nearest = fleet_timezones(fleet.start_time)
    new_pilots = (
        onboarding_counts(fleet, own_timezones)
        if not fleet.invite_only and fleet.status == "pending"
        else {}
    )
    empty = {"total": 0, "in_timezone": 0}
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
        can_reping=can_reping(request.user, fleet),
        thread_url=thread_url(fleet),
        invite_only=fleet.invite_only,
        onboarding_first_week=new_pilots.get("first_week", empty)["total"],
        onboarding_more_fleets=new_pilots.get("more_fleets", empty)["total"],
        onboarding_first_week_in_timezone=new_pilots.get("first_week", empty)[
            "in_timezone"
        ],
        onboarding_more_fleets_in_timezone=new_pilots.get(
            "more_fleets", empty
        )["in_timezone"],
        fleet_timezones=own_timezones,
        timezones_nearest=nearest,
        can_choose_timezones=can_choose_timezones(request.user, fleet),
    )


def _preview_response(
    preview: dict, onboarding: dict | None = None
) -> WavePreviewResponse:
    return WavePreviewResponse(
        picked=preview["picked"],
        other_timezones=preview["other_timezones"],
        other_timezones_by_bracket=[
            TimezoneCount(**row)
            for row in preview["other_timezones_by_bracket"]
        ],
        picks=[PickCount(**row) for row in preview["picks"]],
        onboarding=[
            OnboardingCount(bucket=bucket, **counts)
            for bucket, counts in (onboarding or {}).items()
        ],
        already_invited=preview["already_invited"],
        new=len(preview["new_user_ids"]),
        will_dm=preview["will_dm"],
        no_discord=len(preview["no_discord_user_ids"]),
        helps=preview["helps"],
        opted_out=preview["opted_out"],
        capped=preview["capped"],
        capped_pilots=[CappedPilot(**row) for row in preview["capped_pilots"]],
    )


def _onboarding(fleet, payload: WaveRequest) -> list[str]:
    """New pilot buckets are for standard fleets only."""
    return [] if fleet.invite_only else list(payload.onboarding)


def post_wave_preview(request, fleet_id: int, payload: WaveRequest):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    timezones = chosen_timezones(request.user, fleet, payload.timezones)
    return _preview_response(
        wave_preview(
            fleet,
            tribe_group_ids=payload.tribe_group_ids,
            corporation_ids=payload.corporation_ids,
            user_ids=payload.user_ids,
            onboarding=_onboarding(fleet, payload),
            timezones=timezones,
        ),
        # The dialog's new pilot rows follow the timezone choice.
        onboarding=(
            onboarding_counts(fleet, timezones)
            if not fleet.invite_only and fleet.status == "pending"
            else None
        ),
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
            onboarding=_onboarding(fleet, payload),
            timezones=chosen_timezones(request.user, fleet, payload.timezones),
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
    if not can_reping(request.user, fleet):
        return 403, None
    try:
        pilots = reping_no_answers(fleet)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 202, RepingResponse(pilots=pilots)


def _pilot_blocks(fleet, user_ids) -> dict[int, tuple[str, dict | None]]:
    """Pilots who can't be invited now: why, and for the weekly cap, the
    invite that counts."""
    user_ids = set(user_ids)
    invited = set(
        EveFleetInvite.objects.filter(
            eve_fleet=fleet, user_id__in=list(user_ids)
        ).values_list("user_id", flat=True)
    )
    if fleet.created_by_id in user_ids:
        invited.add(fleet.created_by_id)
    out = {user_id: ("invited", None) for user_id in invited}
    if is_capped_fleet(fleet):
        rest = user_ids - invited
        opted_out = opted_out_user_ids(rest)
        out.update({user_id: ("opted_out", None) for user_id in opted_out})
        for user_id, row in weekly_invites(rest - opted_out).items():
            out[user_id] = ("capped", row)
    return out


def _block_fields(blocks, user_id: int, name: str) -> dict:
    blocked, row = blocks.get(user_id, (None, None))
    return {
        "blocked": blocked,
        "capped": (
            CappedPilot(user_id=user_id, name=name, **row) if row else None
        ),
    }


def get_invite_candidates(
    request,
    fleet_id: int,
    q: str = "",
    pilots_only: bool = False,
    timezones: str = "",
):
    """Tribe groups, corporations and pilots matching ``q``, for the
    pickers. ``pilots_only`` is the Invites tab's one-pilot search.
    ``timezones`` (comma-separated) is the dialog's timezone choice, for
    each group's "in timezone" count."""
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    q = (q or "").strip()
    if len(q) < 2:
        return []
    out: List[InviteCandidate] = []
    if not pilots_only:
        codes = chosen_timezones(
            request.user, fleet, _request_timezones(timezones)
        )
        out += _group_candidates(fleet, q, codes)
    out += _pilot_candidates(fleet, q)
    return out


def _member_counts(members: set[int], brackets, codes) -> dict:
    return {
        "members": len(members),
        "in_timezone": sum(
            1
            for user_id in members
            if codes is None or in_timezones(brackets.get(user_id), codes)
        ),
    }


def _group_candidates(fleet, q: str, codes=None) -> List[InviteCandidate]:
    # pylint: disable=import-outside-toplevel
    from tribes.models import TribeGroup, TribeGroupMembership

    waves = EveFleetInviteWave.objects.filter(eve_fleet=fleet).values_list(
        "tribe_group_ids", "corporation_ids"
    )
    sent_groups = {i for groups, _ in waves for i in groups or []}
    sent_corps = {i for _, corps in waves for i in corps or []}
    groups = list(
        TribeGroup.objects.filter(is_active=True)
        .filter(Q(name__icontains=q) | Q(tribe__name__icontains=q))
        .select_related("tribe")[:8]
    )
    corps = list(
        EveCorporation.objects.filter(
            Q(name__icontains=q) | Q(ticker__iexact=q)
        ).order_by("name")[:6]
    )
    group_members: dict[int, set[int]] = defaultdict(set)
    for user_id, group_id in TribeGroupMembership.objects.filter(
        tribe_group_id__in=[g.id for g in groups],
        status=TribeGroupMembership.STATUS_ACTIVE,
        user__is_active=True,
    ).values_list("user_id", "tribe_group_id"):
        group_members[group_id].add(user_id)
    corp_members: dict[int, set[int]] = defaultdict(set)
    for user_id, corp_id in EveCharacter.objects.filter(
        corporation_id__in=[c.corporation_id for c in corps],
        user__is_active=True,
    ).values_list("user_id", "corporation_id"):
        corp_members[corp_id].add(user_id)
    brackets = brackets_for(
        set().union(*group_members.values(), *corp_members.values())
    )
    out: List[InviteCandidate] = []
    for group in groups:
        out.append(
            InviteCandidate(
                kind="tribe_group",
                id=group.id,
                name=f"{group.tribe.name} · {group.name}",
                detail="Tribe group",
                blocked="invited" if group.id in sent_groups else None,
                **_member_counts(group_members[group.id], brackets, codes),
            )
        )
    for corp in corps:
        out.append(
            InviteCandidate(
                kind="corporation",
                id=corp.corporation_id,
                name=corp.name,
                detail=f"[{corp.ticker}]" if corp.ticker else "Corporation",
                blocked=(
                    "invited" if corp.corporation_id in sent_corps else None
                ),
                **_member_counts(
                    corp_members[corp.corporation_id], brackets, codes
                ),
            )
        )
    return out


def _pilot_candidates(fleet, q: str) -> List[InviteCandidate]:
    out: List[InviteCandidate] = []
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
    blocks = _pilot_blocks(fleet, {c.user_id for c in characters})
    tags = timezone_tags_for({c.user_id for c in characters})
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
                timezone=tags.get(character.user_id),
                **_block_fields(
                    blocks, character.user_id, character.character_name
                ),
            )
        )
    return out


def post_resolve_names(request, fleet_id: int, payload: ResolveNamesRequest):
    """Match a paste of character or Discord names to pilots for the wave
    form."""
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    try:
        resolved = resolve_invite_names(payload.text)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    user_ids = {row["id"] for row in resolved["matched"]}
    blocks = _pilot_blocks(fleet, user_ids)
    tags = timezone_tags_for(user_ids)
    return ResolveNamesResponse(
        matched=[
            ResolvedPilot(
                **row,
                timezone=tags.get(row["id"]),
                **_block_fields(blocks, row["id"], row["name"]),
            )
            for row in resolved["matched"]
        ],
        not_found=resolved["not_found"],
    )


ROUTES = (
    (
        "get",
        "/{fleet_id}/invites",
        {
            "auth": AuthBearer(),
            "response": {200: FleetInvitesResponse, 404: None},
            "description": (
                "A fleet's invited pilots and answers, for its FC (and "
                "Strategic FCs on a private fleet). first_viewed_at (the "
                "leak trace) is null unless the fleet is private and the "
                "caller is a Strategic FC."
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
            "description": (
                "Who a send with these picks would reach. Group, "
                "corporation and new pilot picks only reach pilots who play "
                "in the chosen timezones (the fleet's own by default)."
            ),
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
                "a task at about one a second; one bulk send at a time. "
                "On a standard fleet, pilots who turned invites off or were "
                "invited to a standard fleet this week are skipped; the "
                "pilots' accounts are locked while the send checks them, so "
                "two sends can't both invite one pilot."
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
                "DM everyone who hasn't answered once more. Private fleets "
                "only, sent by a Strategic FC. At most once every 15 "
                "minutes per fleet."
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
            "description": (
                "Tribe groups, corporations and pilots to invite, with why "
                "each can't be invited now (blocked)."
            ),
        },
        get_invite_candidates,
    ),
    (
        "post",
        "/{fleet_id}/invites/resolve",
        {
            "auth": AuthBearer(),
            "response": {
                200: ResolveNamesResponse,
                400: ErrorResponse,
                404: None,
            },
            "description": (
                "Match a paste of primary character names or Discord "
                "usernames to pilots for the Invite pilots dialog."
            ),
        },
        post_resolve_names,
    ),
)
