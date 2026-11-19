"""Poll every character's notifications into ``EveCharacterNotification``."""

from __future__ import annotations

import logging

from django.utils import timezone

from app.celery import app
from eveonline.helpers import notifications
from eveonline.models import EveCharacter
from eveonline.utils import get_esi_downtime_countdown

logger = logging.getLogger(__name__)


@app.task(expires=60, cooldown=50)
def poll_character_notifications(current_minute: int | None = None) -> int:
    """Queue this minute's tenth of the roster.

    Every character with the scope is read once every 10 minutes. A missed
    minute is not caught up: the next cycle reads the same notifications.
    """
    if get_esi_downtime_countdown() > 0:
        return 0
    if current_minute is None:
        current_minute = timezone.now().minute

    character_ids = notifications.character_ids_for_minute(current_minute)
    for index, character_id in enumerate(character_ids):
        fetch_character_notifications.apply_async(
            args=[character_id], countdown=index % 60
        )
    return len(character_ids)


@app.task(expires=10 * 60, cooldown=5 * 60)
def fetch_character_notifications(character_id: int) -> dict:
    """Fetch and store one character's notifications."""
    if get_esi_downtime_countdown() > 0:
        return {"polled": 0, "stored": 0, "skipped": 1}
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if character is None:
        return {"polled": 0, "stored": 0, "skipped": 1}
    return notifications.fetch_notifications(character)
