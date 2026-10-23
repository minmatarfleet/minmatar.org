"""Private (invite-only) fleets: waves of invites, answers and ship targets.

A Strategic FC creates the fleet with ``invite_only``, then sends waves of
invites to tribe groups, corporations or pilots. Each new player gets one
Discord DM (sent by a paced task, fleets.tasks.send_fleet_invite_wave) with
I'm in and Sitting out. I'm in is volunteering ships on the fleet page;
Sitting out is one click. Pilots who are in join the fleet's private
coordination thread (fleets.helpers.private_fleet_discord).
See docs/fleets/private-fleets.md.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
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
OPSEC_LINE = (
    "Invite only. Don't mention this fleet in any channel, on comms or in "
    "chat."
)


class PrivateFleetError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# --- Who a wave reaches ----------------------------------------------------


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
) -> dict:
    """Who a wave would reach: new players, who can't be DM'd, and how many
    of them own a hull for each ship target."""
    picked = (
        _tribe_group_user_ids(tribe_group_ids)
        | _corporation_user_ids(corporation_ids)
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
    with_discord = set(
        DiscordUser.objects.filter(user_id__in=new).values_list(
            "user_id", flat=True
        )
    )
    no_discord = sorted(new - with_discord)
    return {
        "picked": len(picked),
        "already_invited": len(picked & already),
        "new_user_ids": sorted(new),
        "no_discord_user_ids": no_discord,
        "will_dm": len(with_discord),
        "helps": target_owner_counts(fleet, new),
    }


def send_wave(
    fleet: EveFleet,
    *,
    sent_by,
    tribe_group_ids=(),
    corporation_ids=(),
    user_ids=(),
    note: str = "",
) -> EveFleetInviteWave:
    """Invite the new players in these picks and queue their DMs."""
    if not fleet.invite_only:
        raise PrivateFleetError("This fleet isn't invite only")
    if fleet.status in ("complete", "cancelled"):
        raise PrivateFleetError("This fleet has ended")
    if sending_wave(fleet):
        raise PrivateFleetError(
            "The last wave is still sending", status_code=409
        )
    preview = wave_preview(
        fleet,
        tribe_group_ids=tribe_group_ids,
        corporation_ids=corporation_ids,
        user_ids=user_ids,
    )
    new = preview["new_user_ids"]
    if not new:
        raise PrivateFleetError("Nobody new to invite in these picks")
    if len(new) > MAX_WAVE_SIZE:
        raise PrivateFleetError(
            f"A wave can reach at most {MAX_WAVE_SIZE} players"
        )
    no_discord = set(preview["no_discord_user_ids"])
    with transaction.atomic():
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
        )
        EveFleetInvite.objects.bulk_create(
            [
                EveFleetInvite(
                    eve_fleet=fleet,
                    wave=wave,
                    user_id=user_id,
                    dm_delivered=False if user_id in no_discord else None,
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
    if not fleet.invite_only:
        return None
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


def sit_out(invite: EveFleetInvite) -> EveFleetInvite:
    """Sitting out: clear the pilot's ships and record the answer."""
    fleet = invite.eve_fleet
    if fleet.status in ("complete", "cancelled") or (fleet.status == "active"):
        raise PrivateFleetError("This fleet has already started")
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
