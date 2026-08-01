"""Auth helpers for loyalty buyback endpoints."""

from groups.helpers.feature_access import can_use_feature


def can_manage_buyback(user) -> bool:
    return can_use_feature(user, "industry.loyalty.manage") or user.is_staff
