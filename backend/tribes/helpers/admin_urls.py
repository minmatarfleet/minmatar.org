"""URL builders for tribes admin custom views."""

from django.urls import reverse
from django.utils.http import urlencode


def changelist_url(model_name: str, **filters: str | int) -> str:
    url = reverse(f"admin:tribes_{model_name}_changelist")
    if not filters:
        return url
    return f"{url}?{urlencode(filters)}"


def add_url(model_name: str, **initial: str | int) -> str:
    url = reverse(f"admin:tribes_{model_name}_add")
    if not initial:
        return url
    return f"{url}?{urlencode(initial)}"
