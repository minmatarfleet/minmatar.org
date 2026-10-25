"""Fleet invites, answers and ship targets.

Any fleet's FC can invite pilots: new pilots from the alliance health
onboarding lists, tribe groups, corporations or pilots by name. Each new
player gets one Discord DM (sent by a paced task,
fleets.tasks.send_fleet_invite_wave) with I'm in and Sitting out. I'm in is
volunteering ships on the fleet page (or I'm in with no ship yet); Sitting
out is one click.

On a standard fleet an invite is a nudge: a pilot gets at most
``WEEKLY_INVITE_CAP`` fleet invite a week, whoever sends it, and can turn
them off ("Stop fleet invites"). A send locks the pilots' accounts while it
checks and records invites, so two FCs sending at once can't both invite
the same pilot. A private fleet (``invite_only``) is made by a Strategic FC;
its invites ignore both and don't count, carry the opsec line, and pilots
who are in join its private coordination thread
(fleets.helpers.private_fleet_discord). See docs/fleets/private-fleets.md.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCharacterAsset
from fleets.models import (
    EveFleet,
    EveFleetInvite,
    EveFleetInviteWave,
    EveFleetShipTarget,
    EveFleetShipVolunteer,
)

# One wave reaches at most this many players.
MAX_WAVE_SIZE = 300
# Re-ping no answers at most this often per fleet.
REPING_COOLDOWN = timedelta(minutes=15)
# Paste-a-list resolves at most this many names in one go.
MAX_RESOLVE_NAMES = 50
# Standard fleet invites a pilot can get in a rolling week, from any FC.
# Private fleet invites don't count and aren't limited.
WEEKLY_INVITE_CAP = 1
INVITE_CAP_WINDOW = timedelta(days=7)
# The notification preference a pilot turns off with Stop fleet invites.
INVITE_NOTIFICATION_TYPE = "fleets.invite"
ONBOARDING_BUCKETS = (
    EveFleetInvite.SOURCE_FIRST_WEEK,
    EveFleetInvite.SOURCE_MORE_FLEETS,
)
OPSEC_LINE = (
    "Invite only. Don't mention this fleet in any channel, on comms or in "
    "chat."
)


class PrivateFleetError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# --- Who a send reaches ----------------------------------------------------


def is_capped_fleet(fleet: EveFleet) -> bool:
    """Standard fleets, whose invites count against the weekly cap and
    respect Stop fleet invites."""
    return not fleet.invite_only


def weekly_invites(user_ids, now=None) -> dict[int, dict]:
    """Pilots who already got ``WEEKLY_INVITE_CAP`` standard fleet invites
    in the last week: user_id -> the latest invite's ``fleet`` title and
    ``invited_at``, and ``free_at``, when they can be invited again. An
    invite counts once it's made, unless its DM couldn't be delivered."""
    if not user_ids:
        return {}
    since = (now or timezone.now()) - INVITE_CAP_WINDOW
    rows = (
        EveFleetInvite.objects.filter(
            eve_fleet__invite_only=False,
            user_id__in=list(user_ids),
            created_at__gte=since,
        )
        .exclude(dm_delivered=False)
        .order_by("created_at")
        .values_list(
            "user_id",
            "created_at",
            "eve_fleet_id",
            "eve_fleet__objective",
            "eve_fleet__description",
        )
    )
    by_user: dict[int, list] = defaultdict(list)
    for row in rows:
        by_user[row[0]].append(row)
    out: dict[int, dict] = {}
    for user_id, invites in by_user.items():
        if len(invites) < WEEKLY_INVITE_CAP:
            continue
        # Free again once enough of the oldest invites leave the window.
        oldest_kept = invites[len(invites) - WEEKLY_INVITE_CAP]
        _, invited_at, fleet_id, objective, description = invites[-1]
        out[user_id] = {
            "fleet": objective
            or (description or "")[:80]
            or f"Fleet {fleet_id}",
            "invited_at": invited_at,
            "free_at": oldest_kept[1] + INVITE_CAP_WINDOW,
        }
    return out


def capped_user_ids(user_ids, now=None) -> set[int]:
    """Pilots who already got their standard fleet invites this week."""
    return set(weekly_invites(user_ids, now=now))


def opted_out_user_ids(user_ids) -> set[int]:
    """Pilots who pressed Stop fleet invites (or turned them off in Account
    › Notifications)."""
    # pylint: disable=import-outside-toplevel
    from notifications.models import (
        NotificationChannel,
        NotificationPreference,
    )

    if not user_ids:
        return set()
    return set(
        NotificationPreference.objects.filter(
            user_id__in=list(user_ids),
            notification_type=INVITE_NOTIFICATION_TYPE,
            channel=NotificationChannel.DISCORD,
            enabled=False,
        ).values_list("user_id", flat=True)
    )


def stop_fleet_invites(user) -> None:
    # pylint: disable=import-outside-toplevel
    from notifications.models import (
        NotificationChannel,
        NotificationPreference,
    )

    NotificationPreference.objects.update_or_create(
        user=user,
        notification_type=INVITE_NOTIFICATION_TYPE,
        channel=NotificationChannel.DISCORD,
        defaults={"enabled": False},
    )


def onboarding_user_ids(buckets=ONBOARDING_BUCKETS) -> dict[int, str]:
    """New pilots by alliance health onboarding bucket (the health page's
    "Needs first week fleet invite" and "Needs more fleet invites"), from
    the latest snapshot. user_id -> bucket."""
    # pylint: disable=import-outside-toplevel
    from alliance.endpoints.health.schemas import onboarding_from_payload
    from alliance.helpers.health import latest_snapshot

    wanted = [b for b in buckets if b in ONBOARDING_BUCKETS]
    if not wanted:
        return {}
    snap = latest_snapshot()
    if snap is None or not snap.payload:
        return {}
    out: dict[int, str] = {}
    for bucket in wanted:
        for pilot in onboarding_from_payload(snap.payload, bucket).pilots:
            out.setdefault(pilot.user_id, bucket)
    return out


def onboarding_counts(fleet: EveFleet) -> dict[str, int]:
    """How many pilots in each onboarding bucket aren't invited to this
    fleet yet."""
    by_user = onboarding_user_ids()
    invited = set(
        EveFleetInvite.objects.filter(
            eve_fleet=fleet, user_id__in=list(by_user)
        ).values_list("user_id", flat=True)
    )
    counts = {bucket: 0 for bucket in ONBOARDING_BUCKETS}
    for user_id, bucket in by_user.items():
        if user_id not in invited and user_id != fleet.created_by_id:
            counts[bucket] += 1
    return counts


def _tribe_group_user_ids(tribe_group_ids) -> set[int]:
    # pylint: disable=import-outside-toplevel
    from tribes.models import TribeGroupMembership

    if not tribe_group_ids:
        return set()
    return set(
        TribeGroupMembership.objects.filter(
            tribe_group_id__in=list(tribe_group_ids),
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).values_list("user_id", flat=True)
    )


def _corporation_user_ids(corporation_ids) -> set[int]:
    if not corporation_ids:
        return set()
    return set(
        EveCharacter.objects.filter(
            corporation_id__in=list(corporation_ids), user__isnull=False
        ).values_list("user_id", flat=True)
    )


def wave_preview(
    fleet: EveFleet,
    *,
    tribe_group_ids=(),
    corporation_ids=(),
    user_ids=(),
    onboarding=(),
    now=None,
) -> dict:
    """Who a send would reach: new players, who is skipped (already invited,
    invites off, weekly cap), who can't be DM'd, and how many of them own a
    hull for each ship target."""
    new_pilots = onboarding_user_ids(onboarding) if onboarding else {}
    picked = (
        _tribe_group_user_ids(tribe_group_ids)
        | _corporation_user_ids(corporation_ids)
        | set(new_pilots)
        | set(
            User.objects.filter(
                id__in=list(user_ids), is_active=True
            ).values_list("id", flat=True)
        )
    )
    picked = set(
        User.objects.filter(id__in=picked, is_active=True).values_list(
            "id", flat=True
        )
    )
    already = set(
        EveFleetInvite.objects.filter(
            eve_fleet=fleet, user_id__in=picked
        ).values_list("user_id", flat=True)
    )
    if fleet.created_by_id:
        already.add(fleet.created_by_id)
    new = picked - already
    opted_out: set[int] = set()
    capped: dict[int, dict] = {}
    if is_capped_fleet(fleet):
        opted_out = opted_out_user_ids(new)
        capped = weekly_invites(new - opted_out, now=now)
        new = new - opted_out - set(capped)
    with_discord = set(
        DiscordUser.objects.filter(user_id__in=new).values_list(
            "user_id", flat=True
        )
    )
    no_discord = sorted(new - with_discord)
    return {
        "picked": len(picked),
        "already_invited": len(picked & already),
        "opted_out": len(opted_out),
        "capped": len(capped),
        "capped_pilots": _capped_pilots(capped),
        "new_user_ids": sorted(new),
        "no_discord_user_ids": no_discord,
        "will_dm": len(with_discord),
        "helps": target_owner_counts(fleet, new),
        "onboarding_by_user": {
            u: b for u, b in new_pilots.items() if u in new
        },
    }


# The preview names at most this many pilots skipped for the weekly cap.
MAX_CAPPED_NAMES = 50


def _capped_pilots(capped: dict[int, dict]) -> list[dict]:
    """Pilots skipped for the weekly cap, soonest free first, by their
    primary character's name."""
    if not capped:
        return []
    # pylint: disable=import-outside-toplevel
    from eveonline.helpers.characters.identity import (
        primary_characters_for_users,
    )

    order = sorted(capped, key=lambda u: (capped[u]["free_at"], u))
    order = order[:MAX_CAPPED_NAMES]
    mains = primary_characters_for_users(order)
    names = dict(
        User.objects.filter(id__in=order).values_list("id", "username")
    )
    return [
        {
            "user_id": user_id,
            "name": (
                mains[user_id].character_name
                if user_id in mains
                else names.get(user_id, f"User {user_id}")
            ),
            **capped[user_id],
        }
        for user_id in order
    ]


def invite_sources(
    user_ids,
    *,
    onboarding_by_user: dict[int, str],
    picked_user_ids=(),
    tribe_group_ids=(),
    corporation_ids=(),
) -> dict[int, tuple[str, str]]:
    """Why each pilot is invited: (source_kind, source_name). A new pilot
    bucket wins, then being picked by name, then a tribe group, then a
    corporation."""
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCorporation
    from tribes.models import TribeGroup, TribeGroupMembership

    user_ids = set(user_ids)
    out: dict[int, tuple[str, str]] = {}
    for user_id in user_ids:
        if user_id in onboarding_by_user:
            out[user_id] = (onboarding_by_user[user_id], "")
        elif user_id in set(picked_user_ids):
            out[user_id] = (EveFleetInvite.SOURCE_PILOT, "")
    rest = user_ids - set(out)
    if rest and tribe_group_ids:
        names = {
            g.id: f"{g.tribe.name} · {g.name}"
            for g in TribeGroup.objects.filter(
                id__in=list(tribe_group_ids)
            ).select_related("tribe")
        }
        for user_id, group_id in (
            TribeGroupMembership.objects.filter(
                tribe_group_id__in=list(tribe_group_ids),
                user_id__in=list(rest),
                status=TribeGroupMembership.STATUS_ACTIVE,
            )
            .order_by("tribe_group_id")
            .values_list("user_id", "tribe_group_id")
        ):
            out.setdefault(
                user_id,
                (EveFleetInvite.SOURCE_TRIBE_GROUP, names.get(group_id, "")),
            )
    rest = user_ids - set(out)
    if rest and corporation_ids:
        names = dict(
            EveCorporation.objects.filter(
                corporation_id__in=list(corporation_ids)
            ).values_list("corporation_id", "name")
        )
        for user_id, corp_id in (
            EveCharacter.objects.filter(
                user_id__in=list(rest),
                corporation_id__in=list(corporation_ids),
            )
            .order_by("corporation_id")
            .values_list("user_id", "corporation_id")
        ):
            out.setdefault(
                user_id,
                (EveFleetInvite.SOURCE_CORPORATION, names.get(corp_id, "")),
            )
    return out


def parse_invite_names(text: str) -> list[str]:
    """Split a paste of character or Discord names into unique lines.

    Accepts newlines, commas or semicolons; strips a leading ``@`` and
    surrounding whitespace. Order is kept; duplicates (case-insensitive)
    are dropped.
    """
    raw = (text or "").replace(",", "\n").replace(";", "\n")
    seen: set[str] = set()
    names: list[str] = []
    for line in raw.splitlines():
        name = line.strip().lstrip("@").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _claim_invite_name(
    matched_user: dict,
    claimed: set[str],
    *,
    user_id: int,
    name: str,
    label: str,
    detail: str,
) -> None:
    key = name.casefold()
    if key in claimed:
        return
    claimed.add(key)
    if user_id in matched_user:
        return
    matched_user[user_id] = {
        "kind": "pilot",
        "id": user_id,
        "name": label,
        "detail": detail,
        "matched_as": name,
    }


def _match_invite_characters(
    cleaned: list[str],
    by_key: dict[str, str],
    matched_user: dict,
    claimed: set[str],
) -> None:
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCorporation

    character_q = Q()
    for name in cleaned:
        character_q |= Q(character_name__iexact=name)
    characters = list(
        EveCharacter.objects.filter(character_q)
        .filter(user__isnull=False, user__is_active=True)
        .select_related("user")
    )
    corp_ids = {c.corporation_id for c in characters if c.corporation_id}
    corp_names = dict(
        EveCorporation.objects.filter(corporation_id__in=corp_ids).values_list(
            "corporation_id", "name"
        )
    )
    for character in characters:
        _claim_invite_name(
            matched_user,
            claimed,
            user_id=character.user_id,
            name=by_key.get(
                character.character_name.casefold(), character.character_name
            ),
            label=character.character_name,
            detail=corp_names.get(character.corporation_id, ""),
        )


def _match_invite_discord(
    still: list[str],
    by_key: dict[str, str],
    matched_user: dict,
    claimed: set[str],
) -> None:
    if not still:
        return
    discord_q = Q()
    for name in still:
        discord_q |= (
            Q(discord_tag__iexact=name)
            | Q(discord_tag__istartswith=f"{name}#")
            | Q(user__username__iexact=name)
        )
    for discord_user in DiscordUser.objects.filter(
        discord_q, user__is_active=True
    ).select_related("user"):
        tag = discord_user.discord_tag or ""
        username = tag.split("#", maxsplit=1)[0]
        site_name = discord_user.user.username
        for candidate in (tag, username, site_name):
            key = candidate.casefold()
            if key in by_key and key not in claimed:
                _claim_invite_name(
                    matched_user,
                    claimed,
                    user_id=discord_user.user_id,
                    name=by_key[key],
                    label=username or site_name,
                    detail="Discord",
                )
                break


def _prefer_primary_invite_names(matched_user: dict) -> None:
    # pylint: disable=import-outside-toplevel
    from eveonline.helpers.characters.identity import (
        primary_characters_for_users,
    )

    mains = primary_characters_for_users(list(matched_user))
    for user_id, row in matched_user.items():
        main = mains.get(user_id)
        if main is None:
            continue
        # Prefer the primary's name (alts and Discord usernames still match).
        row["name"] = main.character_name
        if not row["detail"] or row["detail"] == "Discord":
            row["detail"] = ""


def resolve_invite_names(names) -> dict:
    """Match pasted primary-character or Discord usernames to accounts.

    Each name is tried as an EVE character (any linked character), then as a
    Discord tag (``name`` or ``name#discriminator``), then as the site
    username. Returns ``matched`` pilots (one per user, first name wins) and
    ``not_found`` for the rest. Caps at ``MAX_RESOLVE_NAMES``.
    """
    cleaned = parse_invite_names(
        "\n".join(names) if not isinstance(names, str) else names
    )
    if len(cleaned) > MAX_RESOLVE_NAMES:
        raise PrivateFleetError(
            f"Paste at most {MAX_RESOLVE_NAMES} names at a time"
        )
    if not cleaned:
        return {"matched": [], "not_found": []}

    by_key = {name.casefold(): name for name in cleaned}
    matched_user: dict[int, dict] = {}
    claimed: set[str] = set()
    _match_invite_characters(cleaned, by_key, matched_user, claimed)
    still = [n for n in cleaned if n.casefold() not in claimed]
    _match_invite_discord(still, by_key, matched_user, claimed)
    _prefer_primary_invite_names(matched_user)

    matched = sorted(
        matched_user.values(), key=lambda row: row["name"].lower()
    )
    not_found = [n for n in cleaned if n.casefold() not in claimed]
    return {"matched": matched, "not_found": not_found}


def send_wave(
    fleet: EveFleet,
    *,
    sent_by,
    tribe_group_ids=(),
    corporation_ids=(),
    user_ids=(),
    onboarding=(),
    note: str = "",
) -> EveFleetInviteWave:
    """Invite the new players in these picks and queue their DMs."""
    if fleet.status in ("complete", "cancelled"):
        raise PrivateFleetError("This fleet has ended")
    preview = wave_preview(
        fleet,
        tribe_group_ids=tribe_group_ids,
        corporation_ids=corporation_ids,
        user_ids=user_ids,
        onboarding=onboarding,
    )
    new = preview["new_user_ids"]
    if not new:
        raise PrivateFleetError(_nobody_new_message(preview))
    if len(new) > MAX_WAVE_SIZE:
        raise PrivateFleetError(
            f"One send can reach at most {MAX_WAVE_SIZE} players"
        )
    # One pilot's DM can go out beside a bulk send; two bulk sends at once
    # would double the DM rate.
    if len(new) > 1 and sending_wave(fleet):
        raise PrivateFleetError(
            "Your last invites are still sending", status_code=409
        )
    no_discord = set(preview["no_discord_user_ids"])
    with transaction.atomic():
        new = _lock_new_invitees(fleet, new)
        if not new:
            raise PrivateFleetError(
                "Someone else just invited them", status_code=409
            )
        sources = invite_sources(
            new,
            onboarding_by_user=preview["onboarding_by_user"],
            picked_user_ids=user_ids,
            tribe_group_ids=tribe_group_ids,
            corporation_ids=corporation_ids,
        )
        number = (
            EveFleetInviteWave.objects.filter(eve_fleet=fleet).aggregate(
                top=Max("number")
            )["top"]
            or 0
        ) + 1
        wave = EveFleetInviteWave.objects.create(
            eve_fleet=fleet,
            number=number,
            sent_by=sent_by,
            note=(note or "").strip()[:300],
            tribe_group_ids=sorted(set(tribe_group_ids)),
            corporation_ids=sorted(set(corporation_ids)),
            user_ids=sorted(set(user_ids)),
            onboarding=sorted(set(onboarding) & set(ONBOARDING_BUCKETS)),
        )
        EveFleetInvite.objects.bulk_create(
            [
                EveFleetInvite(
                    eve_fleet=fleet,
                    wave=wave,
                    user_id=user_id,
                    dm_delivered=False if user_id in no_discord else None,
                    source_kind=sources.get(user_id, ("", ""))[0],
                    source_name=sources.get(user_id, ("", ""))[1][:128],
                )
                for user_id in new
            ]
        )
        # pylint: disable=import-outside-toplevel
        from discord.outbox import on_commit_enqueue
        from fleets.tasks import send_fleet_invite_wave

        on_commit_enqueue(
            send_fleet_invite_wave,
            (wave.id,),
            context=f"fleet {fleet.id} wave {number}",
        )
    return wave


def _lock_new_invitees(fleet: EveFleet, user_ids) -> list[int]:
    """Lock the pilots' accounts until the send commits, then check them
    again: an FC on another fleet may have invited one since the preview.
    Two sends that share a pilot run one after the other, so the second
    sees the first's invite and skips them. Locking in id order keeps two
    sends from deadlocking. Call inside ``transaction.atomic()``."""
    user_ids = sorted(set(user_ids))
    if is_capped_fleet(fleet):
        list(
            User.objects.select_for_update()
            .filter(id__in=user_ids)
            .order_by("id")
            .values_list("id", flat=True)
        )
    taken = set(
        EveFleetInvite.objects.filter(
            eve_fleet=fleet, user_id__in=user_ids
        ).values_list("user_id", flat=True)
    )
    if is_capped_fleet(fleet):
        rest = set(user_ids) - taken
        opted_out = opted_out_user_ids(rest)
        taken |= opted_out | capped_user_ids(rest - opted_out)
    return [user_id for user_id in user_ids if user_id not in taken]


def _nobody_new_message(preview: dict) -> str:
    if preview["capped"] and not preview["opted_out"]:
        return (
            "Already invited to a fleet this week"
            if preview["picked"] == 1
            else "Everyone you picked was invited to a fleet this week"
        )
    if preview["opted_out"] and preview["picked"] == 1:
        return "This pilot turned off fleet invites"
    if preview["already_invited"] and preview["picked"] == 1:
        return "Already invited"
    return "Nobody new to invite in these picks"


def sending_wave(fleet: EveFleet) -> EveFleetInviteWave | None:
    return (
        EveFleetInviteWave.objects.filter(
            eve_fleet=fleet, finished_at__isnull=True
        )
        .order_by("number")
        .first()
    )


def reping_no_answers(fleet: EveFleet, now=None) -> int:
    """Queue one more DM to everyone who hasn't answered. Returns how many."""
    now = now or timezone.now()
    last = (
        EveFleetInvite.objects.filter(
            eve_fleet=fleet, reminded_at__isnull=False
        )
        .aggregate(last=Max("reminded_at"))
        .get("last")
    )
    if last and now - last < REPING_COOLDOWN:
        raise PrivateFleetError(
            "You re-pinged less than 15 minutes ago", status_code=429
        )
    pending = list(
        EveFleetInvite.objects.filter(
            eve_fleet=fleet,
            answer=EveFleetInvite.ANSWER_PENDING,
            dm_delivered=True,
        ).values_list("id", flat=True)
    )
    if not pending:
        return 0
    EveFleetInvite.objects.filter(id__in=pending).update(reminded_at=now)
    # pylint: disable=import-outside-toplevel
    from discord.outbox import on_commit_enqueue
    from fleets.tasks import send_fleet_invite_reminders

    on_commit_enqueue(
        send_fleet_invite_reminders,
        (fleet.id, pending),
        context=f"fleet {fleet.id} re-ping",
    )
    return len(pending)


# --- Answers ---------------------------------------------------------------


def user_invite(fleet: EveFleet, user) -> EveFleetInvite | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return EveFleetInvite.objects.filter(
        eve_fleet=fleet, user_id=user.pk
    ).first()


def record_page_view(fleet: EveFleet, user) -> None:
    """The leak trace: remember the first time an invitee opened the page."""
    if not fleet.invite_only or not getattr(user, "is_authenticated", False):
        return
    EveFleetInvite.objects.filter(
        eve_fleet=fleet, user_id=user.pk, first_viewed_at__isnull=True
    ).update(first_viewed_at=timezone.now())


def _user_volunteer_count(fleet: EveFleet, user_id: int) -> int:
    character_ids = EveCharacter.objects.filter(user_id=user_id).values_list(
        "character_id", flat=True
    )
    return EveFleetShipVolunteer.objects.filter(
        eve_fleet=fleet, character_id__in=list(character_ids)
    ).count()


def sync_answer_from_ships(fleet: EveFleet, user_id: int) -> str | None:
    """After a pilot changes their ships: a ship means I'm in; no ships
    after being in means no answer again. Returns the new answer if it
    changed."""
    invite = EveFleetInvite.objects.filter(
        eve_fleet=fleet, user_id=user_id
    ).first()
    if invite is None:
        return None
    has_ships = _user_volunteer_count(fleet, user_id) > 0
    if has_ships and invite.answer != EveFleetInvite.ANSWER_IN:
        answer = EveFleetInvite.ANSWER_IN
    elif not has_ships and invite.answer == EveFleetInvite.ANSWER_IN:
        answer = EveFleetInvite.ANSWER_PENDING
    else:
        return None
    invite.answer = answer
    invite.answered_at = timezone.now()
    invite.save(update_fields=["answer", "answered_at"])
    _queue_answer_followups(invite)
    return answer


def _check_not_started(fleet: EveFleet) -> None:
    if fleet.status in ("complete", "cancelled", "active"):
        raise PrivateFleetError("This fleet has already started")


def say_in(invite: EveFleetInvite) -> EveFleetInvite:
    """I'm in with no ship yet: the FC sees "No ship yet" and can help."""
    _check_not_started(invite.eve_fleet)
    if invite.answer == EveFleetInvite.ANSWER_IN:
        return invite
    invite.answer = EveFleetInvite.ANSWER_IN
    invite.answered_at = timezone.now()
    invite.save(update_fields=["answer", "answered_at"])
    _queue_answer_followups(invite)
    return invite


def sit_out(invite: EveFleetInvite) -> EveFleetInvite:
    """Sitting out: clear the pilot's ships and record the answer."""
    fleet = invite.eve_fleet
    _check_not_started(fleet)
    character_ids = EveCharacter.objects.filter(
        user_id=invite.user_id
    ).values_list("character_id", flat=True)
    with transaction.atomic():
        EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=list(character_ids)
        ).delete()
        invite.answer = EveFleetInvite.ANSWER_OUT
        invite.answered_at = timezone.now()
        invite.save(update_fields=["answer", "answered_at"])
        _queue_answer_followups(invite)
    return invite


def _queue_answer_followups(invite: EveFleetInvite) -> None:
    """Edit the DM, add to or remove from the thread, refresh the summary."""
    # pylint: disable=import-outside-toplevel
    from discord.outbox import on_commit_enqueue
    from fleets.tasks import sync_private_fleet_invite

    on_commit_enqueue(
        sync_private_fleet_invite,
        (invite.id,),
        context=f"fleet {invite.eve_fleet_id} invite {invite.id}",
    )


# --- Ship targets ----------------------------------------------------------


def _group_ids_by_type(type_ids) -> dict[int, int]:
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveType

    return dict(
        EveType.objects.filter(id__in=list(type_ids)).values_list(
            "id", "eve_group_id"
        )
    )


def _line_matches(target: EveFleetShipTarget, type_id, group_id) -> bool:
    return type_id in set(target.ship_type_ids or []) or (
        group_id is not None and group_id in set(target.group_ids or [])
    )


def volunteer_hulls(fleet: EveFleet) -> list[tuple[int, int]]:
    """(character_id, hull type id) for every ship signed up."""
    rows = EveFleetShipVolunteer.objects.filter(eve_fleet=fleet).values_list(
        "character_id",
        "ship_type_id",
        "fitting__ship_id",
        "fleet_fitting__ship_id",
    )
    return [
        (character_id, hull or fit_ship or fleet_fit_ship)
        for character_id, hull, fit_ship, fleet_fit_ship in rows
        if hull or fit_ship or fleet_fit_ship
    ]


def target_progress(fleet: EveFleet) -> list[dict]:
    """Each target line with how many characters signed up for it."""
    targets = list(EveFleetShipTarget.objects.filter(eve_fleet=fleet))
    if not targets:
        return []
    hulls = volunteer_hulls(fleet)
    groups = _group_ids_by_type({type_id for _, type_id in hulls})
    rows = []
    for target in targets:
        characters = {
            character_id
            for character_id, type_id in hulls
            if _line_matches(target, type_id, groups.get(type_id))
        }
        have = len(characters)
        rows.append(
            {
                "id": target.id,
                "name": target.name,
                "target": target.target,
                "have": have,
                "short": max(target.target - have, 0),
                "ship_type_ids": list(target.ship_type_ids or []),
                "group_ids": list(target.group_ids or []),
            }
        )
    return rows


def target_owner_counts(fleet: EveFleet, user_ids) -> list[dict]:
    """For each target line: how many of these players own a hull for it,
    from their characters' ESI assets."""
    targets = list(EveFleetShipTarget.objects.filter(eve_fleet=fleet))
    if not targets or not user_ids:
        return []
    owned: dict[int, set[int]] = defaultdict(set)
    rows = EveCharacterAsset.objects.filter(
        character__user_id__in=list(user_ids)
    ).values_list("character__user_id", "type_id")
    for user_id, type_id in rows:
        owned[type_id].add(user_id)
    groups = _group_ids_by_type(owned.keys())
    progress = {row["id"]: row for row in target_progress(fleet)}
    out = []
    for target in targets:
        owners = set()
        for type_id, users in owned.items():
            if _line_matches(target, type_id, groups.get(type_id)):
                owners |= users
        out.append(
            {
                "name": target.name,
                "short": progress.get(target.id, {}).get(
                    "short", target.target
                ),
                "own": len(owners),
            }
        )
    return out


def replace_targets(fleet: EveFleet, lines: list[dict]) -> None:
    """Save the FC's target lines, in order. A hull may sit on one line."""
    seen_types: set[int] = set()
    seen_groups: set[int] = set()
    for line in lines:
        types = set(line.get("ship_type_ids") or [])
        groups = set(line.get("group_ids") or [])
        if not (line.get("name") or "").strip():
            raise PrivateFleetError("Every target line needs a name")
        if not types and not groups:
            raise PrivateFleetError(
                f"Add a hull or group to {line['name'].strip()}"
            )
        if types & seen_types or groups & seen_groups:
            raise PrivateFleetError(
                "A hull or group can be on one target line only"
            )
        seen_types |= types
        seen_groups |= groups
    with transaction.atomic():
        EveFleetShipTarget.objects.filter(eve_fleet=fleet).delete()
        EveFleetShipTarget.objects.bulk_create(
            [
                EveFleetShipTarget(
                    eve_fleet=fleet,
                    name=line["name"].strip()[:64],
                    target=int(line["target"]),
                    order=index,
                    ship_type_ids=sorted(set(line.get("ship_type_ids") or [])),
                    group_ids=sorted(set(line.get("group_ids") or [])),
                )
                for index, line in enumerate(lines)
            ]
        )


# --- Declassify ------------------------------------------------------------


def declassify(fleet: EveFleet, now=None) -> EveFleet:
    if not fleet.invite_only:
        raise PrivateFleetError("This fleet isn't private")
    if fleet.declassified_at:
        raise PrivateFleetError("This fleet is already declassified")
    if fleet.status not in ("complete", "cancelled") and (
        fleet.start_time > (now or timezone.now())
    ):
        raise PrivateFleetError("Declassify a fleet once it's over")
    fleet.declassified_at = now or timezone.now()
    fleet.save(update_fields=["declassified_at"])
    return fleet


# --- The Invites tab -------------------------------------------------------


def invite_totals(fleet: EveFleet) -> dict:
    invites = EveFleetInvite.objects.filter(eve_fleet=fleet)
    characters_in = 0
    in_users = list(
        invites.filter(answer=EveFleetInvite.ANSWER_IN).values_list(
            "user_id", flat=True
        )
    )
    if in_users:
        character_ids = EveCharacter.objects.filter(
            user_id__in=in_users
        ).values_list("character_id", flat=True)
        characters_in = (
            EveFleetShipVolunteer.objects.filter(
                eve_fleet=fleet, character_id__in=list(character_ids)
            )
            .values("character_id")
            .distinct()
            .count()
        )
    return {
        "invited": invites.count(),
        "in": len(in_users),
        "characters_in": characters_in,
        "out": invites.filter(answer=EveFleetInvite.ANSWER_OUT).count(),
        "pending": invites.filter(
            answer=EveFleetInvite.ANSWER_PENDING
        ).count(),
    }
