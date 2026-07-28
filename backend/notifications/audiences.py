"""Reusable audience resolvers for broadcast notification types."""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth import get_user_model

from notifications.models import NotificationTopicSubscription

User = get_user_model()


def topic_subscribers(notification_type: str) -> set[int]:
    return set(
        NotificationTopicSubscription.objects.filter(
            notification_type=notification_type
        ).values_list("user_id", flat=True)
    )


def union_audiences(*user_id_sets: Iterable[int]) -> set[int]:
    out: set[int] = set()
    for s in user_id_sets:
        out.update(int(uid) for uid in s if uid)
    return out


def users_from_ids(user_ids: Iterable[int]):
    ids = list(union_audiences(user_ids))
    if not ids:
        return User.objects.none()
    return User.objects.filter(id__in=ids)
