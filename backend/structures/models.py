from django.db import models

from eveonline.models import EveCorporation


# Create your models here.
class EveStructure(models.Model):
    """
    Object for tracking structures
    """

    structure_states = (
        ("anchoring", "Anchoring"),
        ("armor_reinforce", "Armor Reinforce"),
        ("armor_vulnerable", "Armor Vulnerable"),
        ("deploy_vulnerable", "Deploy Vulnerable"),
        ("fitting_invulnerable", "Fitting Invulnerable"),
        ("hull_reinforce", "Hull Reinforce"),
        ("hull_vulnerable", "Hull Vulnerable"),
        ("online_deprecated", "Online Deprecated"),
        ("onlining_vulnerable", "Onlining Vulnerable"),
        ("shield_vulnerable", "Shield Vulnerable"),
        ("unanchored", "Unanchored"),
        ("unknown", "Unknown"),
    )
    id = models.BigIntegerField(primary_key=True)
    system_id = models.BigIntegerField()
    system_name = models.CharField(max_length=255)
    type_id = models.BigIntegerField()
    type_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    reinforce_hour = models.IntegerField()
    fuel_expires = models.DateTimeField(null=True)
    state = models.CharField(
        max_length=255, choices=structure_states, default="unknown"
    )
    state_timer_start = models.DateTimeField(null=True)
    state_timer_end = models.DateTimeField(null=True)
    fitting = models.TextField(blank=True, null=True)
    is_valid_staging = models.BooleanField(default=False)

    corporation = models.ForeignKey(
        EveCorporation,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(f"{self.corporation.name} - {self.name}")
