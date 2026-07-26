"""Feature scope types for PilotFeature evaluation."""

from django.db import models


class FeatureScope(models.TextChoices):
    AFFILIATION = "affiliation", "Affiliation"
    TRIBE_MEMBERSHIP = "tribe_membership", "Tribe membership"
    TRIBE_GROUP_TARGET = "tribe_group_target", "Tribe group target"
    TRIBE_CHIEF = "tribe_chief", "Tribe chief"
    RESOURCE_MATCH = "resource_match", "Resource match"
    AUTH_GROUP = "auth_group", "Auth group"
    STAFF = "staff", "Staff"
