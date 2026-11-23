"""Fleet-scoped voice grants, worked out from a Mumble fleet's own data.

Each sync adds, updates and expires grants to match the fleet: a pilot who
backs out loses theirs. All of them end together when the lease is
released (``voice.leases.release``). Co-FC grants come from
the fleet page (``voice.endpoints``) and are never touched here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveCharacter
from feed.constants import CAPITAL_SHIP_GROUPS
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInvite,
)
from groups.helpers.feature_access import can_use_feature
from voice.access import main_character_ids
from voice.models import VoiceAuditEvent, VoiceChannelLease, VoiceGrant

LOGISTICS_GROUPS = frozenset({"Logistics", "Logistics Frigate"})
# A member row counts as in the fleet when the latest poll touched it.
POLL_SLACK = timedelta(minutes=2)


@dataclass(frozen=True)
class Wanted:
    character_id: int
    source: str
    role: str = VoiceGrant.ROLE_MEMBER
    logistics: bool = False
    wing_id: int | None = None


def _group_names(type_ids) -> dict[int, str]:
    ids = {int(t) for t in type_ids if t}
    if not ids:
        return {}
    return dict(
        EveType.objects.filter(id__in=ids).values_list("id", "eve_group__name")
    )


def _characters_of_user(user_id) -> list[int]:
    if not user_id:
        return []
    return list(
        EveCharacter.objects.filter(user_id=user_id).values_list(
            "character_id", flat=True
        )
    )


def _trusted_capital_pilot(
    character_id: int, group_name: str, fleet: EveFleet
) -> bool:
    """Capital access comes from trusted hull sources only: a community
    member, or a character with that hull class in our earlier fleets
    (this fleet doesn't count: flying the hull now proves nothing)."""
    character = (
        EveCharacter.objects.filter(character_id=character_id)
        .select_related("user")
        .first()
    )
    if (
        character
        and character.user
        and can_use_feature(character.user, "voice.join")
    ):
        return True
    flown = (
        EveFleetInstanceMember.objects.filter(character_id=character_id)
        .exclude(eve_fleet_instance__eve_fleet=fleet)
        .values_list("ship_type_id", flat=True)
    )
    return group_name in set(_group_names(set(flown)).values())


def _in_fleet(fleet: EveFleet) -> list[Wanted]:
    wanted = []
    instances = EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    )
    for instance in instances:
        members = EveFleetInstanceMember.objects.filter(
            eve_fleet_instance=instance
        )
        if instance.last_updated:
            members = members.filter(
                updated_at__gte=instance.last_updated - POLL_SLACK
            )
        members = list(members)
        groups = _group_names(m.ship_type_id for m in members)
        for member in members:
            group = groups.get(int(member.ship_type_id or 0), "")
            wanted.append(
                Wanted(
                    member.character_id,
                    VoiceGrant.SOURCE_IN_FLEET,
                    logistics=group in LOGISTICS_GROUPS,
                    wing_id=member.wing_id,
                )
            )
            if group in CAPITAL_SHIP_GROUPS and _trusted_capital_pilot(
                member.character_id, group, fleet
            ):
                wanted.append(
                    Wanted(
                        member.character_id,
                        VoiceGrant.SOURCE_CAPITAL,
                        VoiceGrant.ROLE_CAPITAL,
                    )
                )
        if instance.boss_id:
            boss = EveCharacter.objects.filter(
                character_id=instance.boss_id
            ).first()
            boss_chars = set(
                _characters_of_user(boss.user_id if boss else None)
            )
            boss_chars.add(int(instance.boss_id))
            for character_id in boss_chars:
                wanted.append(
                    Wanted(
                        character_id,
                        VoiceGrant.SOURCE_BOSS,
                        VoiceGrant.ROLE_COMMANDER,
                    )
                )
    return wanted


def _volunteers(fleet: EveFleet) -> list[Wanted]:
    wanted = [
        Wanted(character_id, VoiceGrant.SOURCE_VOLUNTEER)
        for character_id in fleet.role_volunteers.values_list(
            "character_id", flat=True
        )
    ]
    volunteers = list(
        fleet.ship_volunteers.select_related("fitting", "fleet_fitting")
    )

    def ship_of(volunteer):
        if volunteer.ship_type_id:
            return volunteer.ship_type_id
        if volunteer.fleet_fitting_id:
            return volunteer.fleet_fitting.ship_id
        if volunteer.fitting_id:
            return volunteer.fitting.ship_id
        return None

    groups = _group_names(ship_of(v) for v in volunteers)
    for volunteer in volunteers:
        group = groups.get(int(ship_of(volunteer) or 0), "")
        wanted.append(
            Wanted(
                volunteer.character_id,
                VoiceGrant.SOURCE_VOLUNTEER,
                logistics=group in LOGISTICS_GROUPS,
            )
        )
        if group in CAPITAL_SHIP_GROUPS and _trusted_capital_pilot(
            volunteer.character_id, group, fleet
        ):
            wanted.append(
                Wanted(
                    volunteer.character_id,
                    VoiceGrant.SOURCE_CAPITAL,
                    VoiceGrant.ROLE_CAPITAL,
                )
            )
    return wanted


def _invites(fleet: EveFleet) -> list[Wanted]:
    """Pilots who said in, except those unsure they'll make it."""
    user_ids = (
        fleet.invites.filter(answer=EveFleetInvite.ANSWER_IN)
        .exclude(confidence=EveFleetInvite.CONFIDENCE_LOW)
        .values_list("user_id", flat=True)
    )
    return [
        Wanted(character_id, VoiceGrant.SOURCE_INVITE)
        for character_id in EveCharacter.objects.filter(
            user_id__in=list(user_ids)
        ).values_list("character_id", flat=True)
    ]


def _creator(fleet: EveFleet) -> list[Wanted]:
    return [
        Wanted(
            character_id, VoiceGrant.SOURCE_CREATOR, VoiceGrant.ROLE_COMMANDER
        )
        for character_id in _characters_of_user(fleet.created_by_id)
    ]


def wanted_grants(fleet: EveFleet) -> list[Wanted]:
    return (
        _creator(fleet)
        + _in_fleet(fleet)
        + _volunteers(fleet)
        + _invites(fleet)
    )


def sync_fleet(fleet: EveFleet) -> set[int]:
    """Add or update the fleet's grants. Returns characters whose access
    changed (so the caller republishes them)."""
    wanted = wanted_grants(fleet)
    # Voice is main-only: what an alt earns goes to the account's main.
    mains = main_character_ids(item.character_id for item in wanted)
    merged: dict[tuple, Wanted] = {}
    for item in wanted:
        character_id = mains.get(int(item.character_id), item.character_id)
        key = (int(character_id), item.source, item.role)
        previous = merged.get(key)
        if previous is None:
            merged[key] = Wanted(
                character_id,
                item.source,
                item.role,
                logistics=item.logistics,
                wing_id=item.wing_id,
            )
        else:
            merged[key] = Wanted(
                character_id,
                item.source,
                item.role,
                logistics=previous.logistics or item.logistics,
                wing_id=item.wing_id or previous.wing_id,
            )

    lease = VoiceChannelLease.active().filter(fleet=fleet).first()
    if lease is not None:
        # A kick lasts for the rest of the lease: the next poll must not
        # grant the pilot straight back.
        kicked = set(
            VoiceAuditEvent.objects.filter(
                kind=VoiceAuditEvent.KIND_KICK,
                fleet_id=fleet.id,
                created_at__gte=lease.started_at,
            ).values_list("character_id", flat=True)
        )
        merged = {k: v for k, v in merged.items() if k[0] not in kicked}

    existing = {
        (g.character_id, g.source, g.role): g
        for g in VoiceGrant.objects.filter(
            fleet=fleet, expires_at__isnull=True
        )
    }
    changed: set[int] = set()
    for key, item in merged.items():
        grant = existing.get(key)
        if grant is None:
            VoiceGrant.objects.update_or_create(
                character_id=key[0],
                fleet=fleet,
                source=item.source,
                role=item.role,
                defaults={
                    "logistics": item.logistics,
                    "wing_id": item.wing_id,
                    "expires_at": None,
                },
            )
            changed.add(key[0])
        elif (
            grant.logistics != item.logistics or grant.wing_id != item.wing_id
        ):
            grant.logistics = item.logistics
            grant.wing_id = item.wing_id
            grant.save(update_fields=["logistics", "wing_id", "updated_at"])
            changed.add(key[0])
    # Pilots who backed out (withdrew, answered Out or low confidence, left
    # the in-game fleet) lose that grant. Co-FCs are managed on the fleet
    # page, never here.
    now = timezone.now()
    for key, grant in existing.items():
        if key in merged or grant.source == VoiceGrant.SOURCE_CO_FC:
            continue
        grant.expires_at = now
        grant.save(update_fields=["expires_at", "updated_at"])
        changed.add(key[0])
    return changed
