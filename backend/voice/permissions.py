"""Who may run a fleet's voice, and who may ban."""

from fleets.endpoints.helpers import is_strategic_fc
from groups.helpers.feature_access import can_use_feature


def is_voice_admin(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return can_use_feature(user, "voice.admin") or is_strategic_fc(user)


def can_manage_voice(user, fleet) -> bool:
    """The fleet's own FC, Strategic FCs and voice admins."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if fleet.created_by_id == user.id:
        return True
    return is_voice_admin(user)
