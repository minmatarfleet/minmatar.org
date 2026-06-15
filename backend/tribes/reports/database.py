"""Optional database alias routing for tribe report queries."""

from contextlib import contextmanager

from django.apps import apps
from django.conf import settings


def validate_report_database(alias: str | None) -> None:
    if alias is None:
        return
    if alias not in settings.DATABASES:
        raise ValueError(f"Unknown database alias: {alias!r}")


@contextmanager
def use_report_database(alias: str | None):
    """Route Model.objects queries to ``alias`` for the duration of the block."""
    validate_report_database(alias)
    if alias is None:
        yield
        return

    original_managers = {}
    for model in apps.get_models():
        manager = getattr(model, "objects", None)
        if manager is not None:
            original_managers[model] = model.objects
            model.objects = manager.using(alias)
    try:
        yield
    finally:
        for model, manager in original_managers.items():
            model.objects = manager
