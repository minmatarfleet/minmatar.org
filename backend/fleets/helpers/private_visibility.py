"""Who may know a private (invite-only) fleet exists.

Until it is declassified, a private fleet is visible to the players invited
to it, its creator, Strategic FCs and superusers. Everyone else gets a 404
for it and never sees it in a list or a count.
See docs/fleets/private-fleets.md.
"""

from __future__ import annotations

from django.db.models import Q


def private_hidden_q(prefix: str = "") -> Q:
    """Fleets that are private and not yet declassified."""
    return Q(
        **{
            f"{prefix}invite_only": True,
            f"{prefix}declassified_at__isnull": True,
        }
    )


def is_hidden_private(fleet) -> bool:
    """True for a private fleet that hasn't been declassified."""
    return bool(
        getattr(fleet, "invite_only", False)
        and getattr(fleet, "declassified_at", None) is None
    )


def _is_strategic_fc(user) -> bool:
    # Imported here: the feature registry imports fleet models.
    from groups.helpers.feature_access import (  # pylint: disable=import-outside-toplevel
        can_use_feature,
    )

    return can_use_feature(user, "fleets.manage_any")


def sees_every_private_fleet(user) -> bool:
    """Superusers and Strategic FCs."""
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    return user.is_superuser or _is_strategic_fc(user)


def is_invited(user, fleet) -> bool:
    """Has this user been invited to the fleet (whatever they answered)?"""
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInvite

    return EveFleetInvite.objects.filter(
        eve_fleet_id=fleet.pk, user_id=user.pk
    ).exists()


def private_fleet_visible_to(user, fleet) -> bool:
    """May this user see this fleet at all? True for any non-private one."""
    if not is_hidden_private(fleet):
        return True
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    if fleet.created_by_id and fleet.created_by_id == user.pk:
        return True
    if sees_every_private_fleet(user):
        return True
    return is_invited(user, fleet)


def listed_private_q(user) -> Q:
    """Private fleets a list may show this user: the ones they said I'm in
    to, plus the ones they created."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInvite

    if not getattr(user, "is_authenticated", False) or not user.pk:
        return Q(pk__in=[])
    ids = EveFleetInvite.objects.filter(
        user_id=user.pk, answer=EveFleetInvite.ANSWER_IN
    ).values_list("eve_fleet_id", flat=True)
    return Q(pk__in=list(ids)) | Q(created_by_id=user.pk)
