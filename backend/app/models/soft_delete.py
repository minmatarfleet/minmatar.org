"""Project-wide soft delete base (django-safedelete)."""

from __future__ import annotations

from typing import Any, Tuple, Type

from safedelete.config import SOFT_DELETE
from safedelete.models import SafeDeleteModel


class MinmatarSoftDeleteModel(SafeDeleteModel):
    """Prefer inheriting this over ``SafeDeleteModel`` directly."""

    class Meta:
        abstract = True

    _safedelete_policy = SOFT_DELETE


def get_or_create_active(
    model: Type[SafeDeleteModel],
    defaults: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Tuple[Any, bool]:
    """
    Like ``get_or_create`` on ``all_objects``; if a soft-deleted row exists,
    applies ``defaults`` and saves (which restores it). Returns ``created=True``
    for genuinely new rows and for restored rows (useful for seed logging).
    """
    defaults = defaults or {}
    obj, created = model.all_objects.get_or_create(defaults=defaults, **kwargs)
    if created:
        return obj, True
    if getattr(obj, "deleted", None) is not None:
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save()
        return obj, True
    return obj, False
