from django.contrib.auth.models import User
from django.db import models

from fittings.models import EveFitting
from fleets.models import EveFleet


class CombatLog(models.Model):
    """
    A combat log relating to a fleet or fitting.
    """

    fleet = models.ForeignKey(
        EveFleet, on_delete=models.SET_NULL, null=True, blank=True
    )

    fitting = models.ForeignKey(
        EveFitting, on_delete=models.SET_NULL, null=True, blank=True
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    log_text = models.TextField()

    character_name = models.CharField(max_length=255, blank=True)
    solar_system_name = models.CharField(max_length=255, blank=True)
