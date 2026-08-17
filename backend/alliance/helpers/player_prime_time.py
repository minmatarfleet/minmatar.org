"""Look up EvePlayer prime_time labels for alliance health cards."""

from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings

from eveonline.models import EvePlayer

PRIME_TIME_LABELS = dict(EvePlayer.prime_choices)
READONLY_ALIAS = "production_readonly"


def _query_labels(user_ids: list[int], using: str) -> dict[int, str]:
    rows = (
        EvePlayer.objects.using(using)
        .filter(user_id__in=user_ids)
        .exclude(prime_time__isnull=True)
        .exclude(prime_time="")
        .values_list("user_id", "prime_time")
    )
    return {
        user_id: PRIME_TIME_LABELS.get(prime_time, prime_time)
        for user_id, prime_time in rows
        if user_id
    }


def prime_time_labels_for_users(user_ids: Iterable[int]) -> dict[int, str]:
    ids = sorted({int(uid) for uid in user_ids if uid})
    if not ids:
        return {}
    found = _query_labels(ids, "default")
    missing = [uid for uid in ids if uid not in found]
    if missing and READONLY_ALIAS in settings.DATABASES:
        found.update(_query_labels(missing, READONLY_ALIAS))
    return found
