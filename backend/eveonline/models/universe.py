"""
Models that EveUniverse doesn't have
"""

from django.db import models


class EveUniverseSchematic(models.Model):
    """
    A planetary industry (PI) factory schematic from ESI.

    Used to get cycle_time for factory pins (schematic_id on the pin).
    Fetched from ESI GET /universe/schematics/{schematic_id}/ and cached here.
    """

    schematic_id = models.IntegerField(primary_key=True)
    schematic_name = models.CharField(max_length=128)
    cycle_time = models.PositiveIntegerField(
        help_text="Time in seconds to complete one factory cycle.",
    )

    class Meta:
        verbose_name = "Universe schematic (PI)"
        verbose_name_plural = "Universe schematics (PI)"

    def __str__(self):
        return f"{self.schematic_name} (schematic_id={self.schematic_id})"
