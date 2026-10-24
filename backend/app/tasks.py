"""Platform tasks: Celery queue health."""

from __future__ import annotations

import logging

from app.celery import app
from app.queue_health import measure_queues, report_queues

logger = logging.getLogger(__name__)


def broker_client():
    """The Redis client behind the Celery broker connection."""
    with app.connection_for_read() as connection:
        return connection.default_channel.client


@app.task(expires=60)
def monitor_queue_health() -> dict:
    """Gauge every queue's depth and oldest wait; warn when one backs up.

    Beat runs it every minute and Sentry watches its check-ins, so a missed
    run means beat or the fast-lane workers are down.
    """
    client = broker_client()
    report = measure_queues(client)
    try:
        unacked = client.hlen("unacked")
    except Exception:  # pylint: disable=broad-exception-caught
        # expected: a broker without kombu's "unacked" hash; no gauge then.
        unacked = None
    report_queues(report, unacked)
    return {name: status.as_dict() for name, status in report.items()}
