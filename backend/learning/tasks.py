"""
Celery tasks for the learning app.

Tasks:
- run_mentor_schedule: every 15 minutes, hand unanswered requests to the
  next mentor, send 24-hour reminders and 48-hour follow-ups, and close
  classes nobody confirmed (docs/learning/mentors.md).
"""

import logging

from app.celery import app
from learning.mentors import service

logger = logging.getLogger(__name__)


@app.task(expires=14 * 60, exclusive=14 * 60)
def run_mentor_schedule():
    """Hand-offs, reminders, follow-ups and unconfirmed closes."""
    result = {
        "handed_off": service.expire_unanswered(),
        "reminded": service.send_reminders(),
        "followed_up": service.send_follow_ups(),
        "closed_unconfirmed": service.close_unconfirmed(),
    }
    logger.info("Mentor schedule: %s", result)
    return result
