from django.contrib.auth.models import User
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
    fuel_expires = models.DateTimeField(null=True, blank=True)
    state = models.CharField(
        max_length=255, choices=structure_states, default="unknown"
    )
    state_timer_start = models.DateTimeField(null=True, blank=True)
    state_timer_end = models.DateTimeField(null=True, blank=True)
    fitting = models.TextField(blank=True, null=True)
    is_valid_staging = models.BooleanField(default=False)

    corporation = models.ForeignKey(
        EveCorporation,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(f"{self.corporation.name} - {self.name}")


class EveStructureTimer(models.Model):
    """
    Object for tracking structure timers
    """

    state_choices = (
        ("anchoring", "Anchoring"),
        ("armor", "Armor"),
        ("hull", "Hull"),
        ("unanchoring", "Unanchoring"),
    )

    type_choices = (
        ("astrahus", "Astrahus"),
        ("fortizar", "Fortizar"),
        ("keepstar", "Keepstar"),
        ("raitaru", "Raitaru"),
        ("azbel", "Azbel"),
        ("sotiyo", "Sotiyo"),
        ("athanor", "Athanor"),
        ("tatara", "Tatara"),
        ("tenebrex_cyno_jammer", "Tenebrex Cyno Jammer"),
        ("pharolux_cyno_beacon", "Pharolux Cyno Beacon"),
        ("ansiblex_jump_gate", "Ansiblex Jump Gate"),
        ("orbital_skyhook", "Orbital Skyhook"),
        ("metenox_moon_drill", "Metenox Moon Drill"),
    )

    name = models.CharField(max_length=255)
    state = models.CharField(max_length=255, choices=state_choices)
    type = models.CharField(max_length=255, choices=type_choices)
    timer = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="structures_created_by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="structures_updated_by",
    )

    system_name = models.CharField(max_length=255)
    corporation_name = models.CharField(max_length=255, null=True, blank=True)
    alliance_name = models.CharField(max_length=255, null=True, blank=True)

    structure = models.ForeignKey(
        EveStructure, on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return str(f"{self.structure.name} - {self.state}")
