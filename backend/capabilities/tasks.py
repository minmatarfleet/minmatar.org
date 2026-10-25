"""
Capability engine tasks. All of them are cheap (seconds) and safe to run
twice; see docs/capabilities/capability-engine-design.md §8.
"""

import logging

from django.db import transaction

from app.celery import app
from capabilities import services

logger = logging.getLogger(__name__)

# Edits often come in bursts (an admin saving a fitting and its inlines);
# the queued copy dedupes, so one run picks them all up.
RECOMPUTE_DELAY_SECONDS = 15


@app.task(exclusive=60 * 60)
def check_sde_build():
    """Daily: load CCP's newest SDE build, then recompute everything."""
    build = services.update_sde_if_new()
    if build is None:
        return None
    recompute_everything()
    return build


def recompute_everything(force: bool = False) -> dict:
    services.refresh_skill_info()
    changed = services.recompute_all_requirements(force=force)
    readiness = services.refresh_readiness()
    capabilities = services.refresh_capabilities()
    return {
        "fittings_changed": len(changed),
        "readiness_rows": readiness,
        "capability_rows": capabilities,
    }


@app.task(expires=60 * 60)
def recompute_fitting_requirements(fitting_id: int):
    """A fitting, its overrides or its doctrines changed."""
    before = services.current_set(fitting_id)
    rs = services.recompute_fitting(fitting_id)
    if rs is None or (before and before.pk == rs.pk):
        if rs is None and before is not None:
            services.refresh_capabilities()
        return
    services.refresh_readiness(fitting_ids=[fitting_id])
    services.refresh_capabilities()


@app.task(expires=6 * 60 * 60)
def refresh_character_readiness(character_pk: int):
    """After a character's skills were synced."""
    services.refresh_readiness(character_pks=[character_pk])
    services.refresh_capabilities(character_pks=[character_pk])


@app.task(exclusive=2 * 60 * 60)
def nightly_capabilities():
    """Empirical stats, readiness, capabilities and account links."""
    result = recompute_everything()
    result["account_links"] = services.refresh_account_links()
    logger.info("Capabilities refreshed: %s", result)
    return result


def queue_fitting_recompute(fitting_id: int) -> None:
    """Queue a recompute after the current transaction commits."""

    def _queue():
        recompute_fitting_requirements.apply_async(
            args=[fitting_id], countdown=RECOMPUTE_DELAY_SECONDS
        )

    transaction.on_commit(_queue)
