"""Pilot feature access evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser

from groups.features.registry import FEATURE_DEFINITIONS
from groups.features.types import FeatureScope
from groups.models import PilotFeature, UserAffiliation, UserCommunityStatus
from tribes.models import TribeGroup, TribeGroupMembership

FEATURE_DENIED_DETAIL = "feature_denied"
_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class _FeatureSnapshot:
    code: str
    scope: str
    legacy_permission: str
    staff_permission: str
    deny_community_statuses: tuple[str, ...]
    affiliation_ids: frozenset[int]
    tribe_group_ids: frozenset[int]
    auth_group_ids: frozenset[int]


_feature_cache: dict[str, _FeatureSnapshot] | None = None
_feature_cache_at: float | None = None


def clear_feature_cache() -> None:
    """Clear the in-process feature cache (for tests)."""
    global _feature_cache, _feature_cache_at  # pylint: disable=global-statement
    _feature_cache = None
    _feature_cache_at = None


def _load_feature_cache() -> dict[str, _FeatureSnapshot]:
    global _feature_cache, _feature_cache_at  # pylint: disable=global-statement
    now = time.monotonic()
    if (
        _feature_cache is not None
        and _feature_cache_at is not None
        and now - _feature_cache_at < _CACHE_TTL_SECONDS
    ):
        return _feature_cache
    features = PilotFeature.objects.filter(is_active=True).prefetch_related(
        "affiliations",
        "tribe_groups",
        "auth_groups",
    )
    snapshots: dict[str, _FeatureSnapshot] = {}
    for feature in features:
        snapshots[feature.code] = _FeatureSnapshot(
            code=feature.code,
            scope=feature.scope,
            legacy_permission=feature.legacy_permission or "",
            staff_permission=feature.staff_permission or "",
            deny_community_statuses=tuple(
                feature.deny_community_statuses or []
            ),
            affiliation_ids=frozenset(
                feature.affiliations.values_list("pk", flat=True)
            ),
            tribe_group_ids=frozenset(
                feature.tribe_groups.values_list("pk", flat=True)
            ),
            auth_group_ids=frozenset(
                feature.auth_groups.values_list("pk", flat=True)
            ),
        )
    _feature_cache = snapshots
    _feature_cache_at = now
    return _feature_cache


def _get_feature(code: str) -> _FeatureSnapshot | None:
    return _load_feature_cache().get(code)


def _feature_affiliation_ids(code: str) -> frozenset[int]:
    feature = _get_feature(code)
    if feature is None:
        return frozenset()
    return feature.affiliation_ids


def tribe_group_configured_affiliation_ids(
    tribe_group,
) -> frozenset[int] | None:
    """Return group M2M PKs when non-empty, else None."""
    cache = getattr(tribe_group, "_prefetched_objects_cache", None)
    if cache is not None and "allowed_affiliations" in cache:
        ids = frozenset(a.pk for a in tribe_group.allowed_affiliations.all())
    else:
        ids = frozenset(
            tribe_group.allowed_affiliations.values_list("pk", flat=True)
        )
    return ids if ids else None


def tribe_group_effective_affiliation_ids(
    tribe_group,
    *,
    feature_code: str,
) -> frozenset[int]:
    """Effective affiliation allowlist for a tribe group (group override or feature)."""
    configured = tribe_group_configured_affiliation_ids(tribe_group)
    if configured is not None:
        return configured
    return _feature_affiliation_ids(feature_code)


def user_affiliation(user):
    if user is None or isinstance(user, AnonymousUser):
        return None
    row = (
        UserAffiliation.objects.filter(user=user)
        .select_related("affiliation")
        .first()
    )
    return row.affiliation if row else None


def user_community_status(user) -> str | None:
    if user is None or isinstance(user, AnonymousUser):
        return None
    try:
        return user.community_status.status
    except UserCommunityStatus.DoesNotExist:
        return None


def _has_legacy_permission(user, permission: str) -> bool:
    if not permission:
        return False
    return user.has_perm(permission)


def _community_status_blocks_scope(feature: _FeatureSnapshot, user) -> bool:
    status = user_community_status(user)
    if not status:
        return False
    return status in feature.deny_community_statuses


def _evaluate_affiliation(feature: _FeatureSnapshot, user) -> bool:
    affiliation = user_affiliation(user)
    if affiliation is None:
        return False
    return affiliation.pk in feature.affiliation_ids


def _evaluate_tribe_membership(
    feature: _FeatureSnapshot, user, tribe_group=None
) -> bool:
    if not feature.tribe_group_ids:
        return False
    qs = TribeGroupMembership.objects.filter(
        user=user,
        status=TribeGroupMembership.STATUS_ACTIVE,
        tribe_group_id__in=feature.tribe_group_ids,
    )
    if tribe_group is not None:
        qs = qs.filter(tribe_group_id=tribe_group.pk)
    return qs.exists()


def _evaluate_tribe_group_target(
    feature: _FeatureSnapshot, user, tribe_group
) -> bool:
    if tribe_group is None:
        return False
    affiliation = user_affiliation(user)
    if affiliation is None:
        return False
    allowed_ids = tribe_group_effective_affiliation_ids(
        tribe_group,
        feature_code=feature.code,
    )
    return affiliation.pk in allowed_ids


def _evaluate_tribe_chief(
    feature: _FeatureSnapshot, user, tribe=None, tribe_group=None
) -> bool:
    staff_perm = feature.staff_permission or feature.legacy_permission
    if staff_perm and _has_legacy_permission(user, staff_perm):
        return True
    if tribe_group is not None:
        if (
            feature.tribe_group_ids
            and tribe_group.pk not in feature.tribe_group_ids
        ):
            return False
        if tribe_group.chief_id == user.pk:
            return True
        return tribe_group.tribe.chief_id == user.pk
    if tribe is not None:
        return tribe.chief_id == user.pk
    if not feature.tribe_group_ids:
        return False
    groups = TribeGroup.objects.filter(
        pk__in=feature.tribe_group_ids
    ).select_related("tribe")
    for group in groups:
        if group.chief_id == user.pk:
            return True
        if group.tribe.chief_id == user.pk:
            return True
    return False


def _user_auth_group_ids(user) -> set[int]:
    return set(user.groups.values_list("pk", flat=True))


def _evaluate_resource_match(feature: _FeatureSnapshot, user, fleet) -> bool:
    if fleet is None:
        return _evaluate_affiliation(feature, user)
    if _evaluate_affiliation(feature, user):
        audience_group_ids = (
            set(fleet.audience.groups.values_list("pk", flat=True))
            if fleet.audience is not None
            else set()
        )
        if not audience_group_ids:
            return True
        user_group_ids = _user_auth_group_ids(user)
        if audience_group_ids & user_group_ids:
            return True
        affiliation = user_affiliation(user)
        if affiliation and affiliation.group_id in audience_group_ids:
            return True
    return False


def _evaluate_auth_group(feature: _FeatureSnapshot, user) -> bool:
    if not feature.auth_group_ids:
        return False
    return bool(_user_auth_group_ids(user) & feature.auth_group_ids)


def _evaluate_staff(feature: _FeatureSnapshot, user) -> bool:
    staff_perm = feature.staff_permission or feature.legacy_permission
    return _has_legacy_permission(user, staff_perm)


def _evaluate_scope(
    feature: _FeatureSnapshot,
    user,
    *,
    tribe=None,
    tribe_group=None,
    fleet=None,
) -> bool:
    scope = feature.scope
    if scope == FeatureScope.AFFILIATION:
        return _evaluate_affiliation(feature, user)
    if scope == FeatureScope.TRIBE_MEMBERSHIP:
        return _evaluate_tribe_membership(
            feature, user, tribe_group=tribe_group
        )
    if scope == FeatureScope.TRIBE_GROUP_TARGET:
        return _evaluate_tribe_group_target(feature, user, tribe_group)
    if scope == FeatureScope.TRIBE_CHIEF:
        return _evaluate_tribe_chief(
            feature, user, tribe=tribe, tribe_group=tribe_group
        )
    if scope == FeatureScope.RESOURCE_MATCH:
        return _evaluate_resource_match(feature, user, fleet)
    if scope == FeatureScope.AUTH_GROUP:
        return _evaluate_auth_group(feature, user)
    if scope == FeatureScope.STAFF:
        return _evaluate_staff(feature, user)
    return False


def can_use_feature(
    user,
    code: str,
    *,
    tribe=None,
    tribe_group=None,
    fleet=None,
    allow_legacy: bool = True,
) -> bool:
    """Return True if the user may use the named feature."""
    if user is None or isinstance(user, AnonymousUser):
        return False
    if not user.is_active:
        return False
    if user.is_superuser:
        return True

    feature = _get_feature(code)
    if feature is None:
        if allow_legacy:
            definition = FEATURE_DEFINITIONS.get(code)
            if definition and definition.legacy_permission:
                return _has_legacy_permission(
                    user, definition.legacy_permission
                )
        return False

    legacy_permission = feature.legacy_permission
    if _community_status_blocks_scope(feature, user):
        if allow_legacy and legacy_permission:
            return _has_legacy_permission(user, legacy_permission)
        return False

    if _evaluate_scope(
        feature,
        user,
        tribe=tribe,
        tribe_group=tribe_group,
        fleet=fleet,
    ):
        return True

    if allow_legacy and legacy_permission:
        return _has_legacy_permission(user, legacy_permission)
    return False


def require_feature(
    user,
    code: str,
    *,
    tribe=None,
    tribe_group=None,
    fleet=None,
    allow_legacy: bool = True,
) -> tuple[int, dict] | None:
    """Return None if allowed, else (403, body) for Ninja endpoints."""
    if can_use_feature(
        user,
        code,
        tribe=tribe,
        tribe_group=tribe_group,
        fleet=fleet,
        allow_legacy=allow_legacy,
    ):
        return None
    return 403, {"detail": FEATURE_DENIED_DETAIL, "feature": code}


def check_feature(request, code: str, **context):
    """Ninja helper: return error response tuple or None."""
    return require_feature(request.user, code, **context)


def user_has_legacy_perm(user, perm: str) -> bool:
    """Active superuser or holder of a Django permission codename."""
    if user is None or isinstance(user, AnonymousUser):
        return False
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(perm)
