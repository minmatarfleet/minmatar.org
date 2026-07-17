from django.db import models
from django.utils import timezone


class IndustrySystemCostIndex(models.Model):
    """
    Cached ESI industry cost indices per solar system.

    Populated by Celery from GET /industry/systems/ (manufacturing + reaction).
    Planner job-install costs read this table instead of calling ESI per request.
    """

    solar_system_id = models.BigIntegerField(primary_key=True)
    manufacturing = models.FloatField(default=0.0)
    reaction = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Industry system cost index"
        verbose_name_plural = "Industry system cost indices"

    def __str__(self) -> str:
        return (
            f"system {self.solar_system_id}: "
            f"mfg={self.manufacturing:.4f} rxn={self.reaction:.4f}"
        )
