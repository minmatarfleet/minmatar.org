"""Move the Fanfest tribe under Pulse as one tribe group.

Fanfest was seeded as its own tribe (``fanfest`` / ``fanfest.attendees``).
It is a Pulse group (``pulse.fanfest``). Memberships stay on the same
group row, so characters, history, ranks, invitations and events come
along. Active members gain the Pulse tribe role and lose the Fanfest
tribe role. Auth changes go through ``user.groups`` so Discord role
sync runs. A Discord failure leaves that pilot on the old role; run
the management command again to retry.

Called from migration 0051 (historical models, no membership signals)
and from ``manage.py move_fanfest_into_pulse`` (live models).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import signals as model_signals
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from discord.models import DiscordRole
from tribes.models import TribeGroupMembership
from tribes.signals import (
    tribe_group_membership_post_save,
    tribe_group_membership_pre_save,
)

logger = logging.getLogger(__name__)

FANFEST_SLUG = "fanfest"
PULSE_SLUG = "pulse"
OLD_CODE = "fanfest.attendees"
NEW_CODE = "pulse.fanfest"
GROUP_NAME = "Fanfest"
TRIBE_AUTH = "Tribe - Fanfest"
PULSE_AUTH = "Tribe - Pulse"
OLD_GROUP_AUTH = "Tribe Group - Fanfest Attendees"
NEW_GROUP_AUTH = "Tribe Group - Fanfest"
SEED_GROUP_DESCRIPTION = "Pilots attending or helping organise EVE Fanfest."
SEED_TRIBE_DESCRIPTION = (
    "Flying out to EVE Fanfest? Meet the pilots going, plan "
    "the trip together, and represent the alliance."
)
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"


class MoveLog:
    def __init__(self):
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        logger.info(message)
        self.lines.append(message)


def move_fanfest_into_pulse(apps, discord_client=None) -> list[str]:
    """Rebuild Fanfest as a Pulse group. Returns log lines."""
    log = MoveLog()
    models = _models(apps)
    pulse = models["Tribe"].objects.filter(slug=PULSE_SLUG).first()
    fanfest = models["Tribe"].objects.filter(slug=FANFEST_SLUG).first()
    groups = _fanfest_groups(models["TribeGroup"], fanfest)
    if pulse is None:
        if fanfest is not None or groups:
            log.info("Pulse tribe missing; leaving Fanfest where it is")
        return log.lines
    if fanfest is None and not groups:
        log.info("No Fanfest tribe or group; nothing to move")
        return log.lines

    primary = _choose_primary(groups)
    if primary is None:
        primary = _create_primary(models, pulse, fanfest, log)
        groups.append(primary)
    else:
        _reshape_primary(models, primary, pulse, fanfest, log)
    _ensure_group_auth(models, primary, discord_client, log)
    primary.refresh_from_db()
    moved_ids = {primary.pk}
    for group in groups:
        if group.pk == primary.pk:
            continue
        group.refresh_from_db()
        if group.code == OLD_CODE:
            _merge_into_primary(models, group, primary, log)
        else:
            _reparent_other(models["TribeGroup"], group, pulse, log)
            moved_ids.add(group.pk)
    _move_volunteers(models, fanfest, pulse, primary, log)
    pulse_auth = _pulse_auth_group(models["Tribe"], pulse, log)
    _backfill_role_holders(models, primary, moved_ids, log)
    _sync_people(models, pulse, pulse_auth, moved_ids, log)
    _retire_tribe(models, fanfest, log)
    _delete_empty_auth(TRIBE_AUTH, log)
    _summarize(models, primary, log)
    return log.lines


def _models(apps):
    def get(app_label, name):
        return apps.get_model(app_label, name)

    def seat_model():
        # Group chiefs became timezone seats after this move was written;
        # migration 0051 runs it on the older TribeGroup.chief schema.
        try:
            return get("tribes", "TribeGroupChief")
        except LookupError:
            return None

    return {
        "ChiefSeat": seat_model(),
        "Tribe": get("tribes", "Tribe"),
        "TribeGroup": get("tribes", "TribeGroup"),
        "Membership": get("tribes", "TribeGroupMembership"),
        "Character": get("tribes", "TribeGroupMembershipCharacter"),
        "History": get("tribes", "TribeGroupMembershipHistory"),
        "CharHistory": get("tribes", "TribeGroupMembershipCharacterHistory"),
        "Rank": get("tribes", "TribeGroupRank"),
        "Requirement": get("tribes", "TribeGroupRequirement"),
        "Invitation": get("tribes", "TribeGroupInvitation"),
        "Volunteer": get("tribes", "TribeChiefVolunteer"),
        "Event": get("tribes", "TribeEvent"),
        "ExternalGuild": get("tribes", "TribeExternalGuild"),
        "EvePlayer": get("eveonline", "EvePlayer"),
        "EvePost": get("posts", "EvePost"),
        "EveFleet": get("fleets", "EveFleet"),
        "IndustryOrder": get("industry", "IndustryOrder"),
        "PilotFeature": get("groups", "PilotFeature"),
        "HelpCategory": get("help_tickets", "HelpRequestCategory"),
    }


def _fanfest_groups(tribe_group, fanfest):
    query = Q(code__in=[OLD_CODE, NEW_CODE]) | Q(code__startswith="fanfest.")
    if fanfest is not None:
        query |= Q(tribe_id=fanfest.pk)
    return list(tribe_group.objects.filter(query).distinct())


def _choose_primary(groups):
    by_code = {group.code: group for group in groups}
    if NEW_CODE in by_code:
        return by_code[NEW_CODE]
    if OLD_CODE in by_code:
        return by_code[OLD_CODE]
    for group in groups:
        if group.name in (GROUP_NAME, "Attendees"):
            return group
    if len(groups) == 1:
        return groups[0]
    return None


def _group_chief_id(models, group):
    """A group's chief (the first timezone seat on the newer schema)."""
    seat = models["ChiefSeat"]
    if seat is None:
        return group.chief_id
    return (
        seat.objects.filter(tribe_group_id=group.pk)
        .order_by("pk")
        .values_list("user_id", flat=True)
        .first()
    )


def _set_group_chief(models, group, user_id):
    """Seat ``user_id`` as the group's chief, or clear every seat (None)."""
    seat = models["ChiefSeat"]
    if seat is None:
        group.chief_id = user_id
        return
    if user_id is None:
        seat.objects.filter(tribe_group_id=group.pk).delete()
        return
    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.chief_regions import FALLBACK_REGION

    seat.objects.get_or_create(
        tribe_group_id=group.pk,
        user_id=user_id,
        defaults={"region": FALLBACK_REGION},
    )


def _create_primary(models, pulse, fanfest, log):
    description = SEED_TRIBE_DESCRIPTION
    content = ""
    channel_id = None
    chief_id = None
    if fanfest is not None:
        description = fanfest.description or description
        content = fanfest.content or ""
        channel_id = fanfest.discord_channel_id
        chief_id = fanfest.chief_id
    primary = models["TribeGroup"].objects.create(
        tribe_id=pulse.pk,
        name=_free_name(models["TribeGroup"], pulse.pk, GROUP_NAME, None),
        code=NEW_CODE,
        description=description,
        content=content,
        discord_channel_id=channel_id,
        is_active=True,
    )
    if chief_id:
        _set_group_chief(models, primary, chief_id)
        primary.save()
    log.info(f"Created Pulse group {primary.code} pk={primary.pk}")
    return primary


def _reshape_primary(models, primary, pulse, fanfest, log):
    tribe_group = models["TribeGroup"]
    primary.tribe_id = pulse.pk
    primary.code = _free_code(tribe_group, NEW_CODE, primary)
    primary.name = _free_name(tribe_group, pulse.pk, GROUP_NAME, primary.pk)
    primary.description = _description(primary, fanfest)
    primary.is_active = True
    if fanfest is not None:
        _copy_tribe_fields(models, primary, fanfest)
    primary.save()
    log.info(
        f"Fanfest group pk={primary.pk} is {primary.name} "
        f"({primary.code}) under Pulse"
    )


def _copy_tribe_fields(models, primary, fanfest):
    if not (primary.content or "").strip() and (fanfest.content or "").strip():
        primary.content = fanfest.content
    if not primary.discord_channel_id and fanfest.discord_channel_id:
        primary.discord_channel_id = fanfest.discord_channel_id
    if not _group_chief_id(models, primary) and fanfest.chief_id:
        _set_group_chief(models, primary, fanfest.chief_id)


def _description(primary, fanfest):
    current = (primary.description or "").strip()
    if current and current != SEED_GROUP_DESCRIPTION:
        return primary.description
    if fanfest is not None and (fanfest.description or "").strip():
        return fanfest.description
    return SEED_TRIBE_DESCRIPTION


def _free_code(tribe_group, preferred, row):
    taken = tribe_group.objects.filter(code=preferred)
    if row is not None:
        taken = taken.exclude(pk=row.pk)
    if not taken.exists():
        return preferred
    base = preferred
    number = 2
    while tribe_group.objects.filter(code=f"{base}-{number}").exists():
        number += 1
    return f"{base}-{number}"


def _free_name(tribe_group, tribe_id, preferred, row_pk):
    def taken(name):
        rows = tribe_group.objects.filter(tribe_id=tribe_id, name=name)
        if row_pk is not None:
            rows = rows.exclude(pk=row_pk)
        return rows.exists()

    if not taken(preferred):
        return preferred
    number = 2
    while taken(f"{preferred} {number}"):
        number += 1
    return f"{preferred} {number}"


def _reparent_other(tribe_group, group, pulse, log):
    suffix = group.code.split(".", 1)[1] if "." in group.code else "group"
    preferred = (
        group.code if group.code.startswith("pulse.") else f"pulse.{suffix}"
    )
    if preferred == NEW_CODE:
        preferred = f"pulse.fanfest-{suffix}"
    group.tribe_id = pulse.pk
    group.code = _free_code(tribe_group, preferred, group)
    group.name = _free_name(tribe_group, pulse.pk, group.name, group.pk)
    group.save()
    log.info(f"Reparented {group.name} under Pulse as {group.code}")


def _merge_into_primary(models, source, primary, log):
    """Fold a duplicate attendees group into the Pulse Fanfest group."""
    log.info(f"Merging {source.code} pk={source.pk} into pk={primary.pk}")
    _move_group_children(models, source, primary, log)
    source_auth_id = source.group_id
    dest_auth = (
        Group.objects.filter(pk=primary.group_id).first()
        if primary.group_id
        else None
    )
    source.group_id = None
    _set_group_chief(models, source, None)
    source.is_active = False
    source.save()
    if source_auth_id and (
        dest_auth is None or source_auth_id != dest_auth.pk
    ):
        source_auth = Group.objects.filter(pk=source_auth_id).first()
        _drain_auth(source_auth, dest_auth, log)
        _delete_empty_auth_group(source_auth, log)
    _delete_group_row(source, log)


def _move_group_children(models, source, primary, log):
    _move_ranks(models, source, primary)
    _move_simple_children(models, source, primary)
    _move_memberships(models, source, primary, log)
    _move_publishers(source, primary)
    _retarget_links(models, source, primary)


def _move_ranks(models, source, primary):
    rank_model = models["Rank"]
    membership = models["Membership"]
    for rank in rank_model.objects.filter(tribe_group_id=source.pk):
        clash = rank_model.objects.filter(
            tribe_group_id=primary.pk, code=rank.code
        ).first()
        if clash is None:
            rank.tribe_group_id = primary.pk
            rank.save(update_fields=["tribe_group"])
            continue
        membership.objects.filter(rank_id=rank.pk).update(rank_id=clash.pk)
        rank.delete()


def _move_simple_children(models, source, primary):
    models["Requirement"].objects.filter(tribe_group_id=source.pk).update(
        tribe_group_id=primary.pk
    )
    models["Event"].objects.filter(tribe_group_id=source.pk).update(
        tribe_group_id=primary.pk
    )
    models["Invitation"].objects.filter(tribe_group_id=source.pk).update(
        tribe_group_id=primary.pk
    )
    models["Volunteer"].objects.filter(tribe_group_id=source.pk).update(
        tribe_id=primary.tribe_id, tribe_group_id=primary.pk
    )
    _move_external_guild(models["ExternalGuild"], source, primary)
    _move_help_category(models["HelpCategory"], source, primary)


def _move_external_guild(external_guild, source, primary):
    binding = external_guild.objects.filter(tribe_group_id=source.pk).first()
    if binding is None:
        return
    if external_guild.objects.filter(tribe_group_id=primary.pk).exists():
        logger.warning(
            "Fanfest move: both groups have an external guild; "
            "left binding pk=%s on the source group",
            binding.pk,
        )
        return
    binding.tribe_group_id = primary.pk
    binding.save(update_fields=["tribe_group"])


def _move_help_category(help_category, source, primary):
    category = help_category.objects.filter(tribe_group_id=source.pk).first()
    if category is None:
        return
    if help_category.objects.filter(tribe_group_id=primary.pk).exists():
        category.tribe_group_id = None
        category.save(update_fields=["tribe_group"])
        return
    category.tribe_group_id = primary.pk
    category.save(update_fields=["tribe_group"])


def _move_memberships(models, source, primary, log):
    membership_model = models["Membership"]
    for membership in membership_model.objects.filter(
        tribe_group_id=source.pk
    ):
        existing = membership_model.objects.filter(
            tribe_group_id=primary.pk, user_id=membership.user_id
        ).first()
        if existing is None:
            _retarget_membership(models, membership, primary)
            continue
        _fold_membership(models, membership, existing, log)


def _retarget_membership(models, membership, primary):
    if membership.rank_id:
        rank = models["Rank"].objects.filter(pk=membership.rank_id).first()
        if rank is None or rank.tribe_group_id != primary.pk:
            membership.rank_id = None
    membership.tribe_group_id = primary.pk
    previous = membership.status
    _save_membership(models, membership, previous)


def _fold_membership(models, source, existing, log):
    """Keep one membership per pilot, preferring the stronger status."""
    if _status_rank(source.status) > _status_rank(existing.status):
        previous = existing.status
        existing.status = source.status
        existing.approved_by_id = (
            source.approved_by_id or existing.approved_by_id
        )
        existing.approved_at = source.approved_at or existing.approved_at
        if source.status != "inactive":
            existing.left_at = None
            existing.removed_by_id = None
        if source.rank_id:
            rank = models["Rank"].objects.filter(pk=source.rank_id).first()
            if (
                rank is not None
                and rank.tribe_group_id == existing.tribe_group_id
            ):
                existing.rank_id = source.rank_id
        _save_membership(models, existing, previous)
        log.info(
            f"Membership: {source.user_id} kept as {existing.status} "
            f"on pk={existing.pk}"
        )
    _move_characters(models, source, existing)
    models["History"].objects.filter(membership_id=source.pk).update(
        membership_id=existing.pk
    )
    models["CharHistory"].objects.filter(membership_id=source.pk).update(
        membership_id=existing.pk
    )
    models["Invitation"].objects.filter(membership_id=source.pk).update(
        membership_id=existing.pk
    )
    source.delete()


def _status_rank(status):
    return {"active": 3, "pending": 2, "inactive": 1}.get(status, 0)


def _move_characters(models, source, existing):
    character_model = models["Character"]
    for row in character_model.objects.filter(membership_id=source.pk):
        already = character_model.objects.filter(
            membership_id=existing.pk, character_id=row.character_id
        ).exists()
        if already:
            row.delete()
            continue
        row.membership_id = existing.pk
        row.save(update_fields=["membership"])


def _save_membership(models, membership, previous_status):
    with _quiet_membership_signals():
        membership.save()
    if previous_status == membership.status:
        return
    reason = "approved" if membership.status == STATUS_ACTIVE else ""
    models["History"].objects.create(
        membership_id=membership.pk,
        from_status=previous_status or "",
        to_status=membership.status,
        reason=reason,
    )


@contextmanager
def _quiet_membership_signals():
    """Membership saves here must not depend on Discord.

    Auth roles are synced afterwards, one pilot at a time, so one failed
    Discord call cannot roll the roster row back.
    """
    pre = {
        "sender": TribeGroupMembership,
        "dispatch_uid": "tribe_group_membership_pre_save",
    }
    post = {
        "sender": TribeGroupMembership,
        "dispatch_uid": "tribe_group_membership_post_save",
    }
    pre_on = model_signals.pre_save.disconnect(
        tribe_group_membership_pre_save, **pre
    )
    post_on = model_signals.post_save.disconnect(
        tribe_group_membership_post_save, **post
    )
    try:
        yield
    finally:
        if pre_on:
            model_signals.pre_save.connect(
                tribe_group_membership_pre_save, **pre
            )
        if post_on:
            model_signals.post_save.connect(
                tribe_group_membership_post_save, **post
            )


def _move_publishers(source, primary):
    for field in (
        "post_publishers",
        "fleet_publishers",
        "event_publishers",
        "allowed_affiliations",
    ):
        source_rel = getattr(source, field, None)
        dest_rel = getattr(primary, field, None)
        if source_rel is None or dest_rel is None:
            continue
        ids = list(source_rel.values_list("pk", flat=True))
        if ids:
            dest_rel.add(*ids)


def _retarget_links(models, source, primary):
    models["EvePost"].objects.filter(host_group_id=source.pk).update(
        host_group_id=primary.pk
    )
    models["EveFleet"].objects.filter(host_group_id=source.pk).update(
        host_group_id=primary.pk
    )
    _swap_m2m(models["EvePost"], "tribe_groups", source, primary)
    _swap_m2m(models["IndustryOrder"], "tribe_groups", source, primary)
    _swap_m2m(models["PilotFeature"], "tribe_groups", source, primary)


def _swap_m2m(model, field, source, primary):
    for row in model.objects.filter(**{field: source}):
        relation = getattr(row, field)
        relation.add(primary)
        relation.remove(source)


def _delete_group_row(group, log):
    try:
        group.delete()
    except (ProtectedError, IntegrityError):
        logger.exception(
            "Fanfest move: could not delete group pk=%s", group.pk
        )
        group.is_active = False
        group.save(update_fields=["is_active"])
        log.info(f"Deactivated group pk={group.pk} instead of deleting it")


def _ensure_group_auth(models, primary, discord_client, log):
    if primary.group_id:
        _rename_auth_group(
            primary.group_id, NEW_GROUP_AUTH, discord_client, log
        )
        return
    existing = Group.objects.filter(name=OLD_GROUP_AUTH).first()
    if existing is None:
        existing = Group.objects.filter(name=NEW_GROUP_AUTH).first()
    if existing is not None and _auth_group_free(
        models["TribeGroup"], existing, primary
    ):
        primary.group_id = existing.pk
        primary.save(update_fields=["group"])
        _rename_auth_group(existing.pk, NEW_GROUP_AUTH, discord_client, log)
        return
    created = _create_auth_group(NEW_GROUP_AUTH, log)
    if created is None:
        return
    primary.group_id = created.pk
    primary.save(update_fields=["group"])
    log.info(f"Linked {NEW_GROUP_AUTH}")


def _auth_group_free(tribe_group, auth_group, primary):
    owners = tribe_group.objects.filter(group_id=auth_group.pk)
    if primary.pk:
        owners = owners.exclude(pk=primary.pk)
    return not owners.exists()


def _rename_auth_group(group_id, new_name, discord_client, log):
    group = Group.objects.filter(pk=group_id).first()
    if group is None:
        return None
    if group.name != new_name:
        clash = (
            Group.objects.filter(name=new_name).exclude(pk=group.pk).first()
        )
        if clash is not None:
            log.info(
                f"Auth group {new_name!r} already exists; leaving {group.name!r}"
            )
        else:
            old_name = group.name
            group.name = new_name
            try:
                # save() marks the surrounding migration transaction for
                # rollback when a signal raises. The savepoint contains that.
                with transaction.atomic():
                    group.save(update_fields=["name"])
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Fanfest move: rename of %s failed", old_name)
                log.info(f"Could not rename auth group {old_name!r}")
                group.name = old_name
            else:
                log.info(f"Renamed auth group {old_name!r} to {new_name!r}")
    _rename_discord_role(group, group.name, discord_client, log)
    return group


def _rename_discord_role(group, new_name, discord_client, log):
    role = DiscordRole.objects.filter(group_id=group.pk).first()
    if role is None:
        return
    if role.name != new_name:
        role.name = new_name
        role.save(update_fields=["name"])
    if discord_client is None or not role.role_id:
        return
    try:
        discord_client.edit_role(role.role_id, new_name)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Fanfest move: Discord rename failed for %s", role.role_id
        )
        log.info(f"Discord rename failed for role {role.role_id}")
    else:
        log.info(f"Discord role {role.role_id} renamed to {new_name!r}")


def _pulse_auth_group(tribe_model, pulse, log):
    if pulse.group_id:
        return Group.objects.filter(pk=pulse.group_id).first()
    existing = Group.objects.filter(name=PULSE_AUTH).first()
    if existing is not None:
        owner = tribe_model.objects.filter(group_id=existing.pk).exclude(
            pk=pulse.pk
        )
        if owner.exists():
            log.info("Tribe - Pulse auth group belongs to another tribe")
            return None
        pulse.group_id = existing.pk
        pulse.save(update_fields=["group"])
        log.info("Linked existing Tribe - Pulse auth group")
        return existing
    created = _create_auth_group(PULSE_AUTH, log)
    if created is None:
        return None
    pulse.group_id = created.pk
    pulse.save(update_fields=["group"])
    log.info("Created Tribe - Pulse auth group")
    return created


def _create_auth_group(name, log):
    """Create an auth group. A Discord failure rolls this savepoint back."""
    try:
        with transaction.atomic():
            group = Group.objects.get_or_create(name=name)[0]
            return group
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Fanfest move: could not create auth group %s", name)
        log.info(f"Could not create auth group {name!r}")
        return None


def _move_volunteers(models, fanfest, pulse, primary, log):
    if fanfest is None:
        return
    now = timezone.now()
    volunteer_model = models["Volunteer"]
    offers = volunteer_model.objects.filter(tribe_id=fanfest.pk)
    for offer in offers:
        _retarget_volunteer(models, offer, pulse, primary, now, log)


def _retarget_volunteer(models, offer, pulse, primary, now, log):
    offer.tribe_id = pulse.pk
    if offer.tribe_group_id is None:
        offer.tribe_group_id = primary.pk
        _close_tribe_seat_offer(models, offer, primary, now, log)
    offer.save()


def _close_tribe_seat_offer(models, offer, primary, now, log):
    volunteer_model = models["Volunteer"]
    if offer.status != STATUS_PENDING:
        return
    seat_filled = bool(_group_chief_id(models, primary))
    duplicate = (
        volunteer_model.objects.filter(
            tribe_group_id=primary.pk,
            user_id=offer.user_id,
            status=STATUS_PENDING,
        )
        .exclude(pk=offer.pk)
        .exists()
    )
    if not seat_filled and not duplicate:
        log.info(f"Volunteer pk={offer.pk} now offers for the Fanfest group")
        return
    offer.status = "closed"
    offer.decided_at = now
    log.info(f"Closed Fanfest tribe-chief offer pk={offer.pk}")


def _backfill_role_holders(models, primary, moved_ids, log):
    """Pilots who hold a Fanfest role but have no membership row still join."""
    membership = models["Membership"]
    for group in models["TribeGroup"].objects.filter(pk__in=moved_ids):
        if not group.group_id:
            continue
        auth = Group.objects.filter(pk=group.group_id).first()
        if auth is None:
            continue
        member_ids = set(
            membership.objects.filter(tribe_group_id=group.pk).values_list(
                "user_id", flat=True
            )
        )
        for user in auth.user_set.all():
            if user.pk not in member_ids:
                _create_active_membership(models, user, group, log)
    tribe_auth = Group.objects.filter(name=TRIBE_AUTH).first()
    if tribe_auth is None:
        return
    for user in tribe_auth.user_set.all():
        has_row = membership.objects.filter(
            user_id=user.pk, tribe_group_id__in=moved_ids
        ).exists()
        if not has_row:
            _create_active_membership(models, user, primary, log)


def _create_active_membership(models, user, group, log):
    membership_model = models["Membership"]
    if membership_model.objects.filter(
        user_id=user.pk, tribe_group_id=group.pk
    ).exists():
        return
    try:
        with _quiet_membership_signals():
            membership = membership_model.objects.create(
                user_id=user.pk,
                tribe_group_id=group.pk,
                status=STATUS_ACTIVE,
                approved_at=timezone.now(),
            )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Fanfest move: could not create membership for user %s", user.pk
        )
        log.info(f"Could not create membership for {user.username}")
        return
    _record_created_membership(models, membership)
    _attach_primary_character(models, membership, user)
    log.info(
        f"Membership: added {user.username} to {group.code} (had the role)"
    )


def _record_created_membership(models, membership):
    models["History"].objects.create(
        membership_id=membership.pk,
        from_status="",
        to_status=STATUS_ACTIVE,
        reason="approved",
    )


def _attach_primary_character(models, membership, user):
    player = models["EvePlayer"].objects.filter(user_id=user.pk).first()
    if player is None or not player.primary_character_id:
        return
    character_model = models["Character"]
    if character_model.objects.filter(
        membership_id=membership.pk, character_id=player.primary_character_id
    ).exists():
        return
    row = character_model.objects.create(
        membership_id=membership.pk,
        character_id=player.primary_character_id,
    )
    models["CharHistory"].objects.create(
        membership_id=membership.pk,
        character_id=row.character_id,
        action="added",
    )


def _sync_people(models, pulse, pulse_auth, moved_ids, log):
    membership = models["Membership"]
    user_ids = set(
        membership.objects.filter(tribe_group_id__in=moved_ids).values_list(
            "user_id", flat=True
        )
    )
    tribe_auth = Group.objects.filter(name=TRIBE_AUTH).first()
    if tribe_auth is not None:
        user_ids.update(tribe_auth.user_set.values_list("id", flat=True))
    groups = {
        group.pk: group
        for group in models["TribeGroup"].objects.filter(pk__in=moved_ids)
    }
    auth_by_group = _auth_by_group(groups)
    for user in User.objects.filter(pk__in=user_ids).order_by("id"):
        _sync_user(
            models,
            user,
            pulse,
            pulse_auth,
            tribe_auth,
            groups,
            auth_by_group,
            log,
        )


def _auth_by_group(groups):
    auth = {}
    for group in groups.values():
        if group.group_id:
            auth[group.pk] = Group.objects.filter(pk=group.group_id).first()
    return auth


def _sync_user(
    models, user, pulse, pulse_auth, tribe_auth, groups, auth_by_group, log
):
    membership = models["Membership"]
    rows = list(
        membership.objects.filter(
            user_id=user.pk, tribe_group_id__in=list(groups)
        )
    )
    active_ids = {
        row.tribe_group_id for row in rows if row.status == STATUS_ACTIVE
    }
    wants_pulse = membership.objects.filter(
        user_id=user.pk,
        status=STATUS_ACTIVE,
        tribe_group__tribe_id=pulse.pk,
    ).exists()
    if wants_pulse:
        if _ensure_auth(user, pulse_auth, log):
            _remove_auth(user, tribe_auth, log)
    else:
        _remove_auth(user, tribe_auth, log)
    for group_id, auth in auth_by_group.items():
        if group_id in active_ids:
            _ensure_auth(user, auth, log)
        elif any(row.tribe_group_id == group_id for row in rows):
            _remove_auth(user, auth, log)
    _remove_rank_auth(models, user, rows, log)


def _remove_rank_auth(models, user, rows, log):
    rank_model = models["Rank"]
    for row in rows:
        if row.status == STATUS_ACTIVE:
            continue
        rank_ids = rank_model.objects.filter(
            tribe_group_id=row.tribe_group_id, group_id__isnull=False
        ).values_list("group_id", flat=True)
        for group_id in rank_ids:
            auth = Group.objects.filter(pk=group_id).first()
            _remove_auth(user, auth, log)


def _ensure_auth(user, group, log):
    if group is None:
        return False
    if user.groups.filter(pk=group.pk).exists():
        return True
    try:
        # groups.add uses atomic(savepoint=False). A Discord error there
        # marks the migration transaction broken unless this savepoint
        # catches it and rolls back only the add.
        with transaction.atomic():
            user.groups.add(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Fanfest move: could not add user %s to %s", user.pk, group.name
        )
        log.info(f"Auth add failed: {user.username} -> {group.name}")
        return False
    log.info(f"Auth add: {user.username} -> {group.name}")
    return True


def _remove_auth(user, group, log):
    if group is None:
        return True
    if not user.groups.filter(pk=group.pk).exists():
        return True
    try:
        with transaction.atomic():
            user.groups.remove(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Fanfest move: could not remove user %s from %s",
            user.pk,
            group.name,
        )
        log.info(f"Auth remove failed: {user.username} <- {group.name}")
        return False
    log.info(f"Auth remove: {user.username} <- {group.name}")
    return True


def _drain_auth(source, dest, log):
    if source is None or dest is None or source.pk == dest.pk:
        return
    for user in list(source.user_set.all()):
        if _ensure_auth(user, dest, log):
            _remove_auth(user, source, log)


def _delete_empty_auth(name, log):
    _delete_empty_auth_group(Group.objects.filter(name=name).first(), log)


def _delete_empty_auth_group(group, log):
    if group is None:
        return
    if group.user_set.exists():
        log.info(f"{group.name} still has members; leaving the role")
        return
    try:
        name = group.name
        with transaction.atomic():
            # Collector SQL skips DiscordRole.delete(), which is what
            # removes the role on Discord. Delete the role row first.
            for role in DiscordRole.objects.filter(group_id=group.pk):
                role.delete()
            group.delete()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Fanfest move: could not delete auth group %s", group.pk
        )
        log.info(f"Could not delete auth group {group.name!r}")
        return
    log.info(f"Deleted empty auth group {name!r}")


def _retire_tribe(models, fanfest, log):
    if fanfest is None:
        return
    fanfest.chief_id = None
    fanfest.group_id = None
    if models["TribeGroup"].objects.filter(tribe_id=fanfest.pk).exists():
        fanfest.is_active = False
        fanfest.save()
        log.info("Deactivated Fanfest tribe; a group still points at it")
        return
    if fanfest.discord_guild_id:
        fanfest.is_active = False
        fanfest.save()
        log.info("Deactivated Fanfest tribe; it still has its own Discord")
        return
    fanfest.delete()
    log.info("Deleted the Fanfest tribe")


def _summarize(models, primary, log):
    primary.refresh_from_db()
    active = (
        models["Membership"]
        .objects.filter(tribe_group_id=primary.pk, status=STATUS_ACTIVE)
        .count()
    )
    log.info(
        f"Fanfest is Pulse group pk={primary.pk} "
        f"code={primary.code} active_members={active}"
    )
