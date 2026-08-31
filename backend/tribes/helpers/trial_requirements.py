"""Off-trial requirements for tribe group applications."""

from groups.helpers.feature_access import user_community_status
from groups.models import UserCommunityStatus
from tribes.models import TribeGroup

OFF_TRIAL_REQUIRED_DETAIL = (
    "This tribe group requires members to be off trial before applying."
)


def user_is_on_trial(user) -> bool:
    return user_community_status(user) == UserCommunityStatus.STATUS_TRIAL


def application_blocked_by_trial(user, tribe_group: TribeGroup) -> bool:
    if not tribe_group.require_off_trial:
        return False
    return user_is_on_trial(user)
