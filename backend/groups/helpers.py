import logging

from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import User

from eveonline.models import EveCorporation
from tribes.models import Tribe, TribeGroup
from users.helpers import offboard_group

from .models import (
    EveCorporationGroup,
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)

logger = logging.getLogger(__name__)

VALID_STATUSES = {"active", "trial", "on_leave"}

PEOPLE_TEAM = "People Team"
TECH_TEAM = "Technology Team"

# Django auth group for Discord / permissions: anyone who is chief of an active tribe.
TRIBE_CHIEF_GROUP_NAME = "Tribe - Chief"

# Group type to display suffix for "Corp <TICKER> [Suffix]"
CORPORATION_GROUP_SUFFIXES = {
    EveCorporationGroup.GROUP_TYPE_MEMBER: "",
    EveCorporationGroup.GROUP_TYPE_RECRUITER: " Recruiter",
    EveCorporationGroup.GROUP_TYPE_DIRECTOR: " Director",
    EveCorporationGroup.GROUP_TYPE_GUNNER: " Gunner",
}


def ensure_corporation_groups_for_corp(
    corporation: EveCorporation,
) -> list[EveCorporationGroup]:
    """
    For a corporation with generate_corporation_groups=True, ensure the four
    Corp <TICKER> groups exist (member, recruiter, director, gunner).
    Creates Django auth groups and EveCorporationGroup rows as needed.
    Returns the list of EveCorporationGroup for this corporation.
    """
    if not corporation.generate_corporation_groups or not corporation.ticker:
        return list(
            EveCorporationGroup.objects.filter(
                corporation=corporation
            ).order_by("group_type")
        )

    base_name = f"Corp {corporation.ticker}"
    created_groups = []

    for group_type, suffix in CORPORATION_GROUP_SUFFIXES.items():
        name = f"{base_name}{suffix}".strip()
        ecg = EveCorporationGroup.objects.filter(
            corporation=corporation, group_type=group_type
        ).first()
        if ecg:
            if ecg.group.name != name:
                ecg.group.name = name
                ecg.group.save(update_fields=["name"])
            continue
        auth_group, _ = AuthGroup.objects.get_or_create(
            name=name, defaults={"name": name}
        )
        ecg = EveCorporationGroup.objects.create(
            group=auth_group,
            corporation=corporation,
            group_type=group_type,
        )
        created_groups.append(ecg)

    return list(
        EveCorporationGroup.objects.filter(corporation=corporation).order_by(
            "group_type"
        )
    )


def offboard_corporation_groups(corporation: EveCorporation) -> None:
    """
    Offboard all corporation groups for this corporation (disconnect signal,
    then delete each auth group so Discord roles are not touched during M2M clear).
    """
    group_ids = list(
        EveCorporationGroup.objects.filter(
            corporation=corporation
        ).values_list("group_id", flat=True)
    )
    for group_id in group_ids:
        offboard_group(group_id)


def _trial_and_on_leave_groups():
    """Get or create Trial and On Leave groups in app context so signals (e.g. Discord role) trigger."""
    trial_group, _ = AuthGroup.objects.get_or_create(name="Trial")
    on_leave_group, _ = AuthGroup.objects.get_or_create(name="On Leave")
    return trial_group, on_leave_group


def process_bulk_community_status_row(
    row, row_num, default_reason, changed_by_user_id=None
):
    """
    Process one CSV row for bulk community status update.
    Returns (applied, not_found_name, error_msg).
    changed_by_user_id: optional User pk for history.changed_by.
    """
    username = (row.get("username") or "").strip()
    status = (row.get("community_status") or "").strip().lower()
    row_reason = (row.get("reason") or default_reason).strip()
    if not username:
        return (False, None, None)
    if status not in VALID_STATUSES:
        return (
            False,
            None,
            f"Row {row_num}: invalid status '{status}' for {username}",
        )
    user = User.objects.filter(username=username).first()
    if not user:
        return (False, username, None)
    ucs, created = UserCommunityStatus.objects.get_or_create(
        user=user, defaults={"status": status}
    )
    if not created and ucs.status != status:
        ucs.status = status
        ucs.save()
    latest = (
        UserCommunityStatusHistory.objects.filter(user=user)
        .order_by("-changed_at")
        .first()
    )
    if latest and changed_by_user_id is not None:
        changed_by = User.objects.filter(pk=changed_by_user_id).first()
        if changed_by:
            latest.changed_by = changed_by
            latest.reason = row_reason or "bulk upload"
            latest.save(update_fields=["changed_by", "reason"])
    sync_user_community_groups(user)
    return (True, None, None)


def sync_user_community_groups(user: User) -> None:
    """
    Set the user's Django groups based on UserCommunityStatus and UserAffiliation.
    Trial: affiliation group + Trial group.
    Active: affiliation group only.
    On Leave: On Leave group only (no affiliation group).
    Only adds/removes groups when membership actually changes to avoid Discord overhead.
    """
    trial_group, on_leave_group = _trial_and_on_leave_groups()
    affiliation = UserAffiliation.objects.filter(user=user).first()
    affiliation_group = affiliation.affiliation.group if affiliation else None

    try:
        ucs = user.community_status
        status = ucs.status
    except UserCommunityStatus.DoesNotExist:
        status = UserCommunityStatus.STATUS_ACTIVE

    # Include ALL affiliation type groups (not just the current one) so that
    # when a user moves from e.g. Alliance → Guest, the old Alliance group is
    # correctly identified as a community group and removed.
    all_affiliation_groups = list(
        AuthGroup.objects.filter(affiliationtype__isnull=False).distinct()
    )
    community_groups = list(
        {g for g in (trial_group, on_leave_group) if g}
        | set(all_affiliation_groups)
    )
    if not community_groups:
        return

    if status == UserCommunityStatus.STATUS_ON_LEAVE:
        desired = {on_leave_group} if on_leave_group else set()
    elif status == UserCommunityStatus.STATUS_TRIAL:
        desired = {g for g in (trial_group, affiliation_group) if g}
    else:
        desired = {affiliation_group} if affiliation_group else set()

    current = set(
        user.groups.filter(
            pk__in=[g.pk for g in community_groups]
        ).values_list("pk", flat=True)
    )
    desired_pks = {g.pk for g in desired}
    to_remove = current - desired_pks
    to_add = desired_pks - current

    if to_remove:
        user.groups.remove(*user.groups.filter(pk__in=to_remove))
    if to_add:
        user.groups.add(*user.groups.model.objects.filter(pk__in=to_add))


def user_in_group_named(user: User, group_name: str) -> bool:
    """Return True if user is in the auth Group with the given name (e.g. for tribe/legacy group checks)."""
    return user.groups.filter(name=group_name).exists()


# Alias for callers that still use "team" naming (e.g. People Team, Technology Team); now checks auth group.
user_in_team = user_in_group_named


def sync_tribe_chief_group_membership() -> None:
    """
    Ensure the Tribe - Chief auth group exists and matches every user who chiefs
    an active tribe or an active tribe group (under an active tribe).
    Removes users who no longer qualify.
    """
    chief_group, _ = AuthGroup.objects.get_or_create(
        name=TRIBE_CHIEF_GROUP_NAME
    )
    tribe_chief_ids = Tribe.objects.filter(
        is_active=True, chief_id__isnull=False
    ).values_list("chief_id", flat=True)
    tribe_group_chief_ids = TribeGroup.objects.filter(
        is_active=True,
        tribe__is_active=True,
        chief_id__isnull=False,
    ).values_list("chief_id", flat=True)
    desired_ids = set(tribe_chief_ids) | set(tribe_group_chief_ids)
    current_ids = set(chief_group.user_set.values_list("id", flat=True))
    to_add = desired_ids - current_ids
    to_remove = current_ids - desired_ids
    if to_remove:
        for user in User.objects.filter(pk__in=to_remove):
            user.groups.remove(chief_group)
    if to_add:
        for user in User.objects.filter(pk__in=to_add):
            user.groups.add(chief_group)
    if to_add or to_remove:
        logger.info(
            "sync_tribe_chief_group_membership: added=%s removed=%s",
            len(to_add),
            len(to_remove),
        )
