import logging

from app.celery import app
from surveys.constants import STATUS_OPEN
from surveys.helpers.aggregation import compute_aggregates
from surveys.models import SurveyCampaign

logger = logging.getLogger(__name__)


@app.task()
def snapshot_survey_aggregates(campaign_id: int | None = None):
    """Recompute aggregates for one campaign, or all open campaigns.

    Runs hourly while a survey is open so leadership sees a live view, and is
    also invoked on close.
    """
    if campaign_id is not None:
        campaigns = SurveyCampaign.objects.filter(pk=campaign_id)
    else:
        campaigns = SurveyCampaign.objects.filter(status=STATUS_OPEN)
    total = 0
    for campaign in campaigns:
        try:
            total += compute_aggregates(campaign)
        except Exception:  # pragma: no cover - defensive
            logger.exception("aggregate snapshot failed for %s", campaign.pk)
    return total
