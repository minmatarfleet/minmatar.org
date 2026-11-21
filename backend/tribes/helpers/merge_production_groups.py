"""Merge Capital Production and Subcapital Production into one group.

The survivor is renamed Production (``supply.production``). Each pilot
keeps a single membership. Capital Production and Subcapital Production
become ranks on that group: a pilot in both keeps the capital rank,
because a membership has one rank. Characters, history, requirements,
orders, posts, fleets and chief seats move with them.

Auth changes go through ``user.groups`` after the roster commit, so one
Discord failure cannot roll a membership back. Re-run the management
command to retry those role updates.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import signals as model_signals
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from tribes.helpers.chief_regions import pick_region
from tribes.models import TribeGroupMembership
from tribes.signals import (
    tribe_group_membership_post_save,
    tribe_group_membership_pre_save,
)

logger = logging.getLogger(__name__)

NEW_CODE = "supply.production"
NEW_NAME = "Production"
PRODUCTION_AUTH = "Tribe Group - Production"
CAPITAL_AUTH = "Tribe Group - Capital Production"
SUBCAP_AUTH = "Tribe Group - Subcapital Production"
CAPITAL_CODES = ("supply.capital-production", "industry.capital-production")
SUBCAP_CODES = (
    "supply.subcapital-production",
    "industry.subcapital-production",
)
CAPITAL_RANK = "capital"
SUBCAP_RANK = "subcapital"
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_INACTIVE = "inactive"
STATUS_RANK = {STATUS_ACTIVE: 3, STATUS_PENDING: 2, STATUS_INACTIVE: 1}
TEAM_KIND = "tribe_group"

PRODUCTION_DESCRIPTION = (
    "Ships are ammo, and the big hulls decide wars. Production builds "
    "the subcapital ships the alliance undocks and the capital ships "
    "that decide fights."
)
SEED_DESCRIPTIONS = {
    (
        "Ships are ammo. Subcapital Production ensures the alliance "
        "always has ships in hangars and pilots ready to undock."
    ),
    (
        "Bigger hulls, bigger feeds. Capital Production handles the most "
        "resource-intensive manufacturing the alliance undertakes — the "
        "ships that decide wars."
    ),
}


class MergeLog:
    def __init__(self):
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        logger.info(message)
        self.lines.append(message)


def merge_production_groups(apps) -> list[str]:
    """Fold the two production groups into Production. Returns log lines."""
    log = MergeLog()
    with transaction.atomic():
        state = _merge_roster(apps, log)
    if state is not None:
        _sync_auth(apps, state, log)
    return log.lines


def _models(apps):
    def get(app_label, name):
        return apps.get_model(app_label, name)

    return {
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
        "Chief": get("tribes", "TribeGroupChief"),
        "ExternalGuild": get("tribes", "TribeExternalGuild"),
        "GuildSeat": get("tribes", "TribeExternalGuildSeat"),
        "EvePlayer": get("eveonline", "EvePlayer"),
        "EvePost": get("posts", "EvePost"),
        "EveFleet": get("fleets", "EveFleet"),
        "InviteWave": get("fleets", "EveFleetInviteWave"),
        "IndustryOrder": get("industry", "IndustryOrder"),
        "PilotFeature": get("groups", "PilotFeature"),
        "HelpCategory": get("help_tickets", "HelpRequestCategory"),
        "Audience": get("structures", "LocationAudienceGroup"),
        "Submission": get("structures", "LocationSubmission"),
        "Task": get("taskboard", "Task"),
        "Project": get("taskboard", "Project"),
    }


def _merge_roster(apps, log):
    models = _models(apps)
    groups = _find_groups(models["TribeGroup"])
    if not groups:
        log.info("No capital or subcapital production group; nothing to merge")
        return None

    primary = _choose_primary(groups)
    sources = [group for group in groups if group.pk != primary.pk]
    codes = {group.pk: group.code for group in groups}
    group_ids = list(codes)
    log.info(
        f"Production survivor pk={primary.pk} ({primary.code}); "
        f"folding {[group.code for group in sources]}"
    )

    snapshot = _snapshot(models, group_ids)
    _merge_profile(models, primary, sources, log)
    _move_children(models, sources, primary, log)
    ranks = _ensure_ranks(models, primary, log)
    _merge_memberships(models, groups, primary, codes, ranks, log)
    _assert_preserved(models, primary, snapshot)
    _backfill_role_holders(models, groups, primary, ranks, log)
    state = _link_auth(models, groups, primary, ranks, log)
    _rename_primary(models, primary, log)
    for source in sources:
        _delete_source(models, source, log)
    _assert_no_memberships_left(models, sources)
    _summarize(models, primary, log)
    return state


def _find_groups(tribe_group):
    codes = set(CAPITAL_CODES) | set(SUBCAP_CODES) | {NEW_CODE}
    return list(tribe_group.objects.filter(code__in=codes).order_by("pk"))


def _choose_primary(groups):
    by_code = {group.code: group for group in groups}
    if NEW_CODE in by_code:
        return by_code[NEW_CODE]
    for code in CAPITAL_CODES:
        if code in by_code:
            return by_code[code]
    for code in SUBCAP_CODES:
        if code in by_code:
            return by_code[code]
    return groups[0]


def _snapshot(models, group_ids):
    membership = models["Membership"]
    rows = membership.objects.filter(tribe_group_id__in=group_ids)
    membership_ids = list(rows.values_list("pk", flat=True))
    return {
        "users": set(rows.values_list("user_id", flat=True)),
        "characters": set(
            models["Character"]
            .objects.filter(membership_id__in=membership_ids)
            .values_list("membership__user_id", "character_id")
        ),
        "history": set(
            models["History"]
            .objects.filter(membership_id__in=membership_ids)
            .values_list("pk", flat=True)
        ),
        "char_history": set(
            models["CharHistory"]
            .objects.filter(membership_id__in=membership_ids)
            .values_list("pk", flat=True)
        ),
    }


def _merge_profile(models, primary, sources, log):
    supply = models["Tribe"].objects.filter(slug="supply").first()
    if supply is not None and primary.tribe_id != supply.pk:
        log.info(f"Reparent pk={primary.pk} onto the Supply tribe")
        primary.tribe_id = supply.pk
    _merge_text(primary, sources)
    if not primary.discord_channel_id:
        for source in sources:
            if source.discord_channel_id:
                primary.discord_channel_id = source.discord_channel_id
                log.info(
                    f"Discord channel {source.discord_channel_id} "
                    f"moves from {source.code}"
                )
                break
    else:
        for source in sources:
            channel = source.discord_channel_id
            if channel and channel != primary.discord_channel_id:
                log.info(
                    f"Kept Discord channel {primary.discord_channel_id}; "
                    f"{source.code} also had {channel}"
                )
    primary.is_active = True
    for source in sources:
        _union_m2m(source, primary)


def _merge_text(primary, sources):
    descriptions = []
    contents = []
    for group in [primary, *sources]:
        text = (group.description or "").strip()
        if text and text not in descriptions:
            descriptions.append(text)
        body = (group.content or "").strip()
        if body and body not in contents:
            contents.append(body)
    customs = [text for text in descriptions if text not in SEED_DESCRIPTIONS]
    if customs:
        primary.description = customs[0]
        # A custom blurb stays the description. Anything else that was
        # written on a folded group is kept in the page body.
        extras = customs[1:] + [
            text for text in descriptions if text not in customs
        ]
    else:
        primary.description = PRODUCTION_DESCRIPTION
        extras = []
    for extra in extras:
        if extra and extra not in contents and extra != primary.description:
            contents.append(extra)
    if contents:
        primary.content = "\n\n".join(contents)


def _union_m2m(source, primary):
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


def _move_children(models, sources, primary, log):
    for source in sources:
        _move_simple_children(models, source, primary)
        _move_chiefs(models, source, primary, log)
        _move_volunteers(models, source, primary)
        _move_help_category(models, source, primary, log)
        _move_external_guild(models, source, primary, log)
        _retarget_links(models, source, primary, log)
        _retarget_team_rows(models, source, primary)


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
    for rank in models["Rank"].objects.filter(tribe_group_id=source.pk):
        if rank.code in (CAPITAL_RANK, SUBCAP_RANK):
            continue
        clash = (
            models["Rank"]
            .objects.filter(tribe_group_id=primary.pk, code=rank.code)
            .first()
        )
        if clash is None:
            rank.tribe_group_id = primary.pk
            rank.save(update_fields=["tribe_group"])
            continue
        models["Membership"].objects.filter(rank_id=rank.pk).update(
            rank_id=clash.pk
        )
        rank.delete()


def _move_chiefs(models, source, primary, log):
    seat_model = models["Chief"]
    taken_regions = set(
        seat_model.objects.filter(tribe_group_id=primary.pk).values_list(
            "region", flat=True
        )
    )
    taken_users = set(
        seat_model.objects.filter(tribe_group_id=primary.pk).values_list(
            "user_id", flat=True
        )
    )
    for seat in seat_model.objects.filter(tribe_group_id=source.pk):
        if seat.user_id in taken_users:
            seat.delete()
            continue
        region = pick_region(seat.region, taken_regions)
        if region is None:
            log.info(
                f"Chief user {seat.user_id} from {source.code} stays a "
                "member; Production's three seats are full"
            )
            seat.delete()
            continue
        seat.tribe_group_id = primary.pk
        seat.region = region
        seat.save(update_fields=["tribe_group", "region"])
        taken_regions.add(region)
        taken_users.add(seat.user_id)
        log.info(f"Chief user {seat.user_id} seated as {region}")


def _move_volunteers(models, source, primary):
    now = timezone.now()
    volunteer = models["Volunteer"]
    for offer in volunteer.objects.filter(tribe_group_id=source.pk):
        offer.tribe_id = primary.tribe_id
        offer.tribe_group_id = primary.pk
        if offer.status == STATUS_PENDING:
            duplicate = (
                volunteer.objects.filter(
                    tribe_group_id=primary.pk,
                    user_id=offer.user_id,
                    region=offer.region,
                    status=STATUS_PENDING,
                )
                .exclude(pk=offer.pk)
                .exists()
            )
            if duplicate:
                offer.status = "closed"
                offer.decided_at = now
        offer.save()


def _move_help_category(models, source, primary, log):
    category_model = models["HelpCategory"]
    source_category = category_model.objects.filter(
        tribe_group_id=source.pk
    ).first()
    if source_category is None:
        return
    primary_category = category_model.objects.filter(
        tribe_group_id=primary.pk
    ).first()
    if primary_category is None:
        source_category.tribe_group_id = primary.pk
        source_category.save(update_fields=["tribe_group"])
        log.info(
            f"Help category pk={source_category.pk} now points at Production"
        )
        return
    assignee_ids = list(source_category.assignees.values_list("pk", flat=True))
    if assignee_ids:
        primary_category.assignees.add(*assignee_ids)
    source_category.tribe_group_id = None
    source_category.is_active = False
    source_category.save(update_fields=["tribe_group", "is_active"])
    log.info(
        f"Help category pk={source_category.pk} unlinked; "
        "its tickets stay and its assignees were copied"
    )


def _move_external_guild(models, source, primary, log):
    guild_model = models["ExternalGuild"]
    binding = guild_model.objects.filter(tribe_group_id=source.pk).first()
    if binding is None:
        return
    survivor = guild_model.objects.filter(tribe_group_id=primary.pk).first()
    if survivor is None:
        binding.tribe_group_id = primary.pk
        binding.save(update_fields=["tribe_group"])
        log.info(f"External guild binding pk={binding.pk} moved")
        return
    seat_model = models["GuildSeat"]
    for seat in seat_model.objects.filter(binding_id=binding.pk):
        clash = seat_model.objects.filter(
            binding_id=survivor.pk, discord_user_id=seat.discord_user_id
        ).exists()
        if clash:
            continue
        seat.binding_id = survivor.pk
        seat.save(update_fields=["binding"])
    binding.delete()
    log.info(f"External guild seats folded onto binding pk={survivor.pk}")


def _retarget_links(models, source, primary, log):
    models["EvePost"].objects.filter(host_group_id=source.pk).update(
        host_group_id=primary.pk
    )
    models["EveFleet"].objects.filter(host_group_id=source.pk).update(
        host_group_id=primary.pk
    )
    _swap_m2m(models["EvePost"], "tribe_groups", source, primary)
    _swap_m2m(models["IndustryOrder"], "tribe_groups", source, primary)
    _swap_m2m(models["PilotFeature"], "tribe_groups", source, primary)
    _retarget_audience(models["Audience"], source, primary)
    _rewrite_json_ids(
        models["Submission"], "audience_tribe_group_ids", source, primary
    )
    _rewrite_json_ids(models["InviteWave"], "tribe_group_ids", source, primary)
    log.info(
        f"Retargeted posts, fleets, orders and features from {source.code}"
    )


def _swap_m2m(model, field, source, primary):
    for row in model.objects.filter(**{field: source}):
        relation = getattr(row, field)
        relation.add(primary)
        relation.remove(source)


def _retarget_audience(audience, source, primary):
    for row in audience.objects.filter(tribe_group_id=source.pk):
        clash = audience.objects.filter(
            location_id=row.location_id, tribe_group_id=primary.pk
        ).exclude(pk=row.pk)
        if clash.exists():
            row.delete()
            continue
        row.tribe_group_id = primary.pk
        row.save(update_fields=["tribe_group"])


def _rewrite_json_ids(model, field, source, primary):
    for row in model.objects.iterator():
        values = getattr(row, field) or []
        if source.pk not in values and str(source.pk) not in values:
            continue
        rewritten = []
        for value in values:
            try:
                number = int(value)
            except (TypeError, ValueError):
                rewritten.append(value)
                continue
            if number == source.pk:
                number = primary.pk
            if number not in rewritten:
                rewritten.append(number)
        setattr(row, field, rewritten)
        row.save(update_fields=[field])


def _retarget_team_rows(models, source, primary):
    old_key = f"tribe_group:{source.pk}"
    new_key = f"tribe_group:{primary.pk}"
    old_path = f"/alliance/tribes/{source.tribe_id}/{source.pk}"
    new_path = f"/alliance/tribes/{primary.tribe_id}/{primary.pk}"
    _retarget_tasks(
        models["Task"], source, primary, old_key, new_key, old_path, new_path
    )
    _retarget_projects(models["Project"], source, primary, old_path, new_path)


def _retarget_tasks(
    model, source, primary, old_key, new_key, old_path, new_path
):
    rows = model.objects.filter(
        Q(team_kind=TEAM_KIND, team_id=source.pk)
        | Q(source_key=old_key)
        | Q(link_url__contains=old_path)
    )
    for row in rows:
        if row.source_key == old_key:
            clash = (
                model.objects.filter(
                    rule=row.rule,
                    source_key=new_key,
                    user_id=row.user_id,
                )
                .exclude(pk=row.pk)
                .exists()
            )
            if clash:
                row.delete()
                continue
            row.source_key = new_key
        _retarget_team_fields(row, source, primary, old_path, new_path)
        row.save()


def _retarget_projects(model, source, primary, old_path, new_path):
    rows = model.objects.filter(
        Q(team_kind=TEAM_KIND, team_id=source.pk)
        | Q(link_url__contains=old_path)
    )
    for row in rows:
        _retarget_team_fields(row, source, primary, old_path, new_path)
        row.save()


def _retarget_team_fields(row, source, primary, old_path, new_path):
    if row.team_kind == TEAM_KIND and row.team_id == source.pk:
        row.team_id = primary.pk
        row.team_label = NEW_NAME
    link = row.link_url or ""
    if old_path in link:
        row.link_url = link.replace(old_path, new_path)


def _ensure_ranks(models, primary, log):
    spec = (
        (CAPITAL_RANK, "Capital Production", 0),
        (SUBCAP_RANK, "Subcapital Production", 1),
    )
    ranks = {}
    for code, name, sort_order in spec:
        rank, created = models["Rank"].objects.get_or_create(
            tribe_group_id=primary.pk,
            code=code,
            defaults={"name": name, "sort_order": sort_order},
        )
        if not created and (
            rank.name != name or rank.sort_order != sort_order
        ):
            rank.name = name
            rank.sort_order = sort_order
            rank.save(update_fields=["name", "sort_order"])
        ranks[code] = rank
        if created:
            log.info(f"Rank {name} created")
    return ranks


def _merge_memberships(models, groups, primary, codes, ranks, log):
    membership = models["Membership"]
    user_ids = set(
        membership.objects.filter(
            tribe_group_id__in=[group.pk for group in groups]
        ).values_list("user_id", flat=True)
    )
    for user_id in sorted(user_ids):
        rows = list(
            membership.objects.filter(
                user_id=user_id,
                tribe_group_id__in=[group.pk for group in groups],
            ).order_by("pk")
        )
        if not rows:
            continue
        rank_code = _rank_code(rows, codes)
        keeper = next(
            (row for row in rows if row.tribe_group_id == primary.pk),
            rows[0],
        )
        original_status = keeper.status
        for other in rows:
            if other.pk == keeper.pk:
                continue
            _absorb(models, keeper, other, log)
        _finish_membership(
            models, keeper, primary, ranks, rank_code, original_status, log
        )


def _rank_code(rows, codes):
    """Capital wins when the pilot's strongest rows include it."""
    best = max(STATUS_RANK.get(row.status, 0) for row in rows)
    pool = [row for row in rows if STATUS_RANK.get(row.status, 0) == best]
    pool_codes = [codes.get(row.tribe_group_id, "") for row in pool]
    if any(code in CAPITAL_CODES for code in pool_codes):
        return CAPITAL_RANK
    if any(code in SUBCAP_CODES for code in pool_codes):
        return SUBCAP_RANK
    return None


def _absorb(models, keeper, other, log):
    if STATUS_RANK.get(other.status, 0) > STATUS_RANK.get(keeper.status, 0):
        keeper.status = other.status
        keeper.approved_by_id = other.approved_by_id or keeper.approved_by_id
        keeper.approved_at = other.approved_at or keeper.approved_at
        if other.status != STATUS_INACTIVE:
            keeper.left_at = None
            keeper.removed_by_id = None
        log.info(
            f"Membership: user {keeper.user_id} status "
            f"{other.status} kept from pk={other.pk}"
        )
    elif keeper.status == STATUS_INACTIVE and other.left_at:
        if keeper.left_at is None or other.left_at > keeper.left_at:
            keeper.left_at = other.left_at
            keeper.removed_by_id = other.removed_by_id or keeper.removed_by_id
    if not keeper.requirement_snapshot and other.requirement_snapshot:
        keeper.requirement_snapshot = other.requirement_snapshot
    if other.created_at and (
        keeper.created_at is None or other.created_at < keeper.created_at
    ):
        keeper.created_at = other.created_at
    _move_characters(models, other, keeper)
    models["History"].objects.filter(membership_id=other.pk).update(
        membership_id=keeper.pk
    )
    models["CharHistory"].objects.filter(membership_id=other.pk).update(
        membership_id=keeper.pk
    )
    models["Invitation"].objects.filter(membership_id=other.pk).update(
        membership_id=keeper.pk
    )
    other.delete()


def _move_characters(models, source, keeper):
    character_model = models["Character"]
    for row in character_model.objects.filter(membership_id=source.pk):
        already = character_model.objects.filter(
            membership_id=keeper.pk, character_id=row.character_id
        ).exists()
        if already:
            row.delete()
            continue
        row.membership_id = keeper.pk
        row.save(update_fields=["membership"])


def _finish_membership(
    models, keeper, primary, ranks, rank_code, original_status, log
):
    keeper.tribe_group_id = primary.pk
    if rank_code:
        keeper.rank_id = ranks[rank_code].pk
    elif keeper.rank_id:
        rank = models["Rank"].objects.filter(pk=keeper.rank_id).first()
        if rank is None or rank.tribe_group_id != primary.pk:
            keeper.rank_id = None
    with _quiet_membership_signals():
        keeper.save()
    if original_status == keeper.status:
        return
    reason = "approved" if keeper.status == STATUS_ACTIVE else ""
    models["History"].objects.create(
        membership_id=keeper.pk,
        from_status=original_status or "",
        to_status=keeper.status,
        reason=reason,
    )
    log.info(
        f"Membership: user {keeper.user_id} {original_status} → "
        f"{keeper.status} rank={rank_code or 'unchanged'}"
    )


def _assert_preserved(models, primary, snapshot):
    membership = models["Membership"]
    rows = membership.objects.filter(tribe_group_id=primary.pk)
    users = set(rows.values_list("user_id", flat=True))
    missing_users = snapshot["users"] - users
    if missing_users:
        raise RuntimeError(
            "Production merge dropped users: "
            + ", ".join(str(user_id) for user_id in sorted(missing_users))
        )
    membership_ids = list(rows.values_list("pk", flat=True))
    characters = set(
        models["Character"]
        .objects.filter(membership_id__in=membership_ids)
        .values_list("membership__user_id", "character_id")
    )
    missing_characters = snapshot["characters"] - characters
    if missing_characters:
        raise RuntimeError(
            "Production merge dropped characters: "
            f"{sorted(missing_characters)}"
        )
    history = set(
        models["History"]
        .objects.filter(pk__in=snapshot["history"])
        .values_list("pk", flat=True)
    )
    if history != snapshot["history"]:
        raise RuntimeError("Production merge dropped membership history")
    char_history = set(
        models["CharHistory"]
        .objects.filter(pk__in=snapshot["char_history"])
        .values_list("pk", flat=True)
    )
    if char_history != snapshot["char_history"]:
        raise RuntimeError("Production merge dropped character history")


def _backfill_role_holders(models, groups, primary, ranks, log):
    """A Discord role with no roster row still joins, at that role's rank."""
    seen = set(
        models["Membership"]
        .objects.filter(tribe_group_id=primary.pk)
        .values_list("user_id", flat=True)
    )
    for group, rank_code in (
        (_group_with_codes(groups, CAPITAL_CODES), CAPITAL_RANK),
        (_group_with_codes(groups, SUBCAP_CODES), SUBCAP_RANK),
    ):
        auth = _specialty_auth(group, _auth_name(rank_code))
        if auth is None:
            continue
        for user in auth.user_set.all().order_by("id"):
            if user.pk in seen:
                continue
            _create_active_membership(
                models, user, primary, ranks[rank_code], log
            )
            seen.add(user.pk)


def _group_with_codes(groups, codes):
    for code in codes:
        for group in groups:
            if group.code == code:
                return group
    return None


def _auth_name(rank_code):
    if rank_code == CAPITAL_RANK:
        return CAPITAL_AUTH
    return SUBCAP_AUTH


def _specialty_auth(group, expected_name):
    if group is not None and group.group_id:
        auth = Group.objects.filter(pk=group.group_id).first()
        if auth is not None and auth.name != PRODUCTION_AUTH:
            return auth
    return Group.objects.filter(name=expected_name).first()


def _create_active_membership(models, user, primary, rank, log):
    try:
        with _quiet_membership_signals():
            membership = models["Membership"].objects.create(
                user_id=user.pk,
                tribe_group_id=primary.pk,
                rank_id=rank.pk,
                status=STATUS_ACTIVE,
                approved_at=timezone.now(),
            )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Production merge: could not add role holder %s", user.pk
        )
        log.info(f"Could not add role holder {user.username}")
        return
    models["History"].objects.create(
        membership_id=membership.pk,
        from_status="",
        to_status=STATUS_ACTIVE,
        reason="approved",
    )
    _attach_primary_character(models, membership, user)
    log.info(
        f"Membership: added {user.username} at rank {rank.code} "
        "(held the Discord role)"
    )


def _attach_primary_character(models, membership, user):
    player = models["EvePlayer"].objects.filter(user_id=user.pk).first()
    if player is None or not player.primary_character_id:
        return
    character_model = models["Character"]
    if character_model.objects.filter(
        membership_id=membership.pk,
        character_id=player.primary_character_id,
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


def _link_auth(models, groups, primary, ranks, log):
    capital_auth = _specialty_auth(
        _group_with_codes(groups, CAPITAL_CODES), CAPITAL_AUTH
    )
    subcap_auth = _specialty_auth(
        _group_with_codes(groups, SUBCAP_CODES), SUBCAP_AUTH
    )
    production_auth = _ensure_production_auth(log)
    if production_auth is not None:
        _release_auth(models, capital_auth, production_auth)
        _release_auth(models, subcap_auth, production_auth)
        primary.group_id = production_auth.pk
        _attach_rank_auth(ranks[CAPITAL_RANK], capital_auth, production_auth)
        _attach_rank_auth(ranks[SUBCAP_RANK], subcap_auth, production_auth)
        log.info("Group role is Tribe Group - Production")
    elif capital_auth is not None:
        _release_auth(models, subcap_auth, capital_auth)
        primary.group_id = capital_auth.pk
        _attach_rank_auth(ranks[SUBCAP_RANK], subcap_auth, capital_auth)
        log.info(
            "Could not create the Production role; the group role stays "
            "the capital role until the command is run again"
        )
    elif subcap_auth is not None:
        primary.group_id = subcap_auth.pk
        log.info(
            "Could not create the Production role; the group role stays "
            "the subcapital role until the command is run again"
        )
    return {
        "primary_id": primary.pk,
    }


def _ensure_production_auth(log):
    existing = Group.objects.filter(name=PRODUCTION_AUTH).first()
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            return Group.objects.create(name=PRODUCTION_AUTH)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Production merge: could not create %s", PRODUCTION_AUTH
        )
        log.info(f"Could not create auth group {PRODUCTION_AUTH!r}")
        return None


def _release_auth(models, auth, keep):
    """Free an auth group so a rank or the Production group can own it."""
    if auth is None or (keep is not None and auth.pk == keep.pk):
        return
    models["TribeGroup"].objects.filter(group_id=auth.pk).update(group=None)
    models["Rank"].objects.filter(group_id=auth.pk).update(group=None)


def _attach_rank_auth(rank, auth, group_auth):
    if auth is None or (group_auth is not None and auth.pk == group_auth.pk):
        return
    rank.group_id = auth.pk
    rank.save(update_fields=["group"])


def _rename_primary(models, primary, log):
    primary.name = _free_name(
        models["TribeGroup"], primary.tribe_id, NEW_NAME, primary.pk
    )
    primary.code = _free_code(models["TribeGroup"], NEW_CODE, primary)
    primary.save()
    log.info(f"Renamed pk={primary.pk} to {primary.name} / {primary.code}")


def _free_code(tribe_group, preferred, row):
    taken = tribe_group.objects.filter(code=preferred)
    if row is not None and row.pk:
        taken = taken.exclude(pk=row.pk)
    if not taken.exists():
        return preferred
    number = 2
    while tribe_group.objects.filter(code=f"{preferred}-{number}").exists():
        number += 1
    return f"{preferred}-{number}"


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


def _delete_source(models, source, log):
    source.group_id = None
    source.save(update_fields=["group"])
    models["Rank"].objects.filter(tribe_group_id=source.pk).delete()
    blockers = _relation_counts(source)
    if blockers:
        source.is_active = False
        source.code = _free_code(
            models["TribeGroup"], f"retired.{source.code}"[:64], source
        )
        source.name = _free_name(
            models["TribeGroup"],
            source.tribe_id,
            f"{source.name} (merged)",
            source.pk,
        )
        source.save()
        log.info(f"Deactivated {source.code}; still referenced by {blockers}")
        return
    source_pk = source.pk
    try:
        source.delete()
    except (ProtectedError, IntegrityError):
        logger.exception(
            "Production merge: could not delete group pk=%s", source_pk
        )
        source.is_active = False
        source.code = _free_code(
            models["TribeGroup"], f"retired.{source.code}"[:64], source
        )
        source.save()
        log.info(f"Deactivated group pk={source_pk} instead of deleting it")
        return
    log.info(f"Deleted folded group pk={source_pk}")


def _relation_counts(group):
    """Reverse relations that would block deleting the folded group."""
    counts = []
    for relation in group._meta.related_objects:
        accessor = relation.get_accessor_name()
        try:
            related = getattr(group, accessor)
        except (ObjectDoesNotExist, AttributeError):
            continue
        try:
            count = related.count()
        except (AttributeError, TypeError):
            continue
        if count:
            counts.append(f"{accessor}={count}")
    return counts


def _assert_no_memberships_left(models, sources):
    leftover = models["Membership"].objects.filter(
        tribe_group_id__in=[source.pk for source in sources]
    )
    user_ids = list(leftover.values_list("user_id", flat=True))
    if user_ids:
        raise RuntimeError(
            "Production merge left memberships on a folded group: "
            + ", ".join(str(user_id) for user_id in user_ids)
        )


def _summarize(models, primary, log):
    membership = models["Membership"]
    rows = membership.objects.filter(tribe_group_id=primary.pk)
    counts = {
        status: rows.filter(status=status).count()
        for status in (STATUS_ACTIVE, STATUS_PENDING, STATUS_INACTIVE)
    }
    capital = rows.filter(rank__code=CAPITAL_RANK).count()
    subcap = rows.filter(rank__code=SUBCAP_RANK).count()
    log.info(
        f"Production pk={primary.pk}: "
        f"active={counts[STATUS_ACTIVE]} pending={counts[STATUS_PENDING]} "
        f"inactive={counts[STATUS_INACTIVE]} "
        f"capital rank={capital} subcapital rank={subcap}"
    )


def _sync_auth(apps, state, log):
    models = _models(apps)
    primary = (
        models["TribeGroup"].objects.filter(pk=state["primary_id"]).first()
    )
    if primary is None:
        return
    production_auth = (
        Group.objects.filter(pk=primary.group_id).first()
        if primary.group_id
        else None
    )
    ranks = {
        rank.code: rank
        for rank in models["Rank"].objects.filter(tribe_group_id=primary.pk)
    }
    capital_auth = _rank_auth(ranks.get(CAPITAL_RANK))
    subcap_auth = _rank_auth(ranks.get(SUBCAP_RANK))
    for membership in (
        models["Membership"]
        .objects.filter(tribe_group_id=primary.pk)
        .select_related("user", "rank")
    ):
        _sync_member(
            membership,
            production_auth,
            capital_auth,
            subcap_auth,
            log,
        )


def _rank_auth(rank):
    if rank is None or not rank.group_id:
        return None
    return Group.objects.filter(pk=rank.group_id).first()


def _sync_member(membership, production_auth, capital_auth, subcap_auth, log):
    user = membership.user
    rank_code = membership.rank.code if membership.rank_id else ""
    if rank_code == CAPITAL_RANK:
        rank_auth, other_auth = capital_auth, subcap_auth
    elif rank_code == SUBCAP_RANK:
        rank_auth, other_auth = subcap_auth, capital_auth
    else:
        rank_auth, other_auth = None, None
    if membership.status == STATUS_ACTIVE:
        _ensure_auth(user, production_auth, log)
        _ensure_auth(user, rank_auth, log)
        if other_auth is not None and (
            production_auth is None or other_auth.pk != production_auth.pk
        ):
            _remove_auth(user, other_auth, log)
        return
    if membership.status != STATUS_INACTIVE:
        return
    for auth in (production_auth, capital_auth, subcap_auth):
        _remove_auth(user, auth, log)


def _ensure_auth(user, group, log):
    if group is None or user.groups.filter(pk=group.pk).exists():
        return True
    try:
        with transaction.atomic():
            user.groups.add(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Production merge: could not add user %s to %s",
            user.pk,
            group.name,
        )
        log.info(f"Auth add failed: {user.username} -> {group.name}")
        return False
    log.info(f"Auth add: {user.username} -> {group.name}")
    return True


def _remove_auth(user, group, log):
    if group is None or not user.groups.filter(pk=group.pk).exists():
        return True
    try:
        with transaction.atomic():
            user.groups.remove(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Production merge: could not remove user %s from %s",
            user.pk,
            group.name,
        )
        log.info(f"Auth remove failed: {user.username} <- {group.name}")
        return False
    log.info(f"Auth remove: {user.username} <- {group.name}")
    return True


@contextmanager
def _quiet_membership_signals():
    """Roster writes here must not depend on Discord."""
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
