"""Timezone assessment and Discord role upkeep. See docs/timezones.md."""

import logging

from app.celery import app
from timezones import discord_roles, services

logger = logging.getLogger(__name__)


@app.task(exclusive=60 * 60)
def assess_timezones():
    """Every 6 hours: reassess every pilot, then reconcile Discord roles.

    Changed pilots get their roles straight away through
    pilot_timezone_changed; the reconcile retries anything that failed.
    """
    results = services.assess_users()
    outcome = discord_roles.apply_roles()
    logger.info(
        "Assessed %d pilot timezones; roles %s", len(results), dict(outcome)
    )
    return {"assessed": len(results), "roles": dict(outcome)}


@app.task(expires=60 * 60)
def assess_user_timezone(user_id: int):
    """One pilot, after they change their declared prime time."""
    services.assess_users([user_id])
