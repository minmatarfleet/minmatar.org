"""Keep tribe chiefs represented as active members of each tribe group."""

import logging

from django.utils import timezone

from tribes.models import Tribe, TribeGroup, TribeGroupMembership

logger = logging.getLogger(__name__)


def ensure_tribe_chiefs_have_group_memberships() -> int:
    """
    For every active tribe with a chief, ensure the chief has an active
    TribeGroupMembership in each active TribeGroup under that tribe.

    Creates memberships or upgrades pending/inactive rows so chiefs count as
    members (API checks, Discord auth groups via post_save).

    Returns the number of memberships created or updated.
    """
    now = timezone.now()
    changed = 0

    tribes = Tribe.objects.filter(
        is_active=True, chief_id__isnull=False
    ).select_related("chief")
    tribe_ids = [t.pk for t in tribes]
    if not tribe_ids:
        return 0

    groups_by_tribe: dict[int, list[TribeGroup]] = {}
    for tg in TribeGroup.objects.filter(
        tribe_id__in=tribe_ids, is_active=True
    ).order_by("pk"):
        groups_by_tribe.setdefault(tg.tribe_id, []).append(tg)

    for tribe in tribes:
        chief = tribe.chief
        for tg in groups_by_tribe.get(tribe.pk, ()):
            membership, created = TribeGroupMembership.objects.get_or_create(
                user=chief,
                tribe_group=tg,
                defaults={
                    "status": TribeGroupMembership.STATUS_ACTIVE,
                    "approved_at": now,
                    "approved_by": chief,
                },
            )
            if created:
                changed += 1
                continue
            if membership.status == TribeGroupMembership.STATUS_ACTIVE:
                continue
            membership.status = TribeGroupMembership.STATUS_ACTIVE
            membership.approved_at = now
            membership.approved_by = chief
            membership.left_at = None
            membership.removed_by = None
            membership.history_changed_by = chief
            membership.history_inactive_reason = ""
            membership.save()
            changed += 1

    if changed:
        logger.info(
            "ensure_tribe_chiefs_have_group_memberships: updated_or_created=%s",
            changed,
        )
    return changed
