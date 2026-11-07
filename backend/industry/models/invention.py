"""Invention recipes and decryptors, loaded from CCP's static data export.

eveuniverse stores invention materials and products but not the success
chance, so the planner keeps its own copy of the invention activity. Rows
are replaced as a whole by ``industry.helpers.invention_sde`` whenever CCP
publishes a new SDE build.
"""

from django.db import models


class InventionOutcome(models.Model):
    """One possible result of an invention job.

    ``source_type_id`` is what the job consumes one of per attempt: a T1
    blueprint (one copy run) or an ancient relic. A source can list several
    outcomes (Squall: Deluge or Torrent; a relic: any of four hulls); the
    player picks one when starting the job.
    """

    SOURCE_T1_BLUEPRINT = "t1_blueprint"
    SOURCE_RELIC = "relic"
    SOURCE_CHOICES = (
        (SOURCE_T1_BLUEPRINT, "T1 blueprint copy"),
        (SOURCE_RELIC, "Ancient relic"),
    )

    source_type_id = models.IntegerField(db_index=True)
    source_name = models.CharField(max_length=200, default="")
    source_kind = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    # T1 product of the source blueprint (its copy job's EIV basis).
    source_product_type_id = models.IntegerField(null=True, blank=True)
    # Copy time of one run of the source blueprint (T1 only).
    copy_time_seconds = models.IntegerField(default=0)
    # The T2/T3 blueprint copy a success produces, and what it builds.
    blueprint_type_id = models.IntegerField(db_index=True)
    product_type_id = models.IntegerField(db_index=True)
    probability = models.FloatField()
    # Runs on each invented copy (SDE ``quantity``).
    runs = models.IntegerField()
    time_seconds = models.IntegerField()
    # [[type_id, quantity], ...] consumed per attempt (datacores).
    materials = models.JSONField(default=list)
    encryption_skill_id = models.IntegerField(null=True, blank=True)
    science_skill_ids = models.JSONField(default=list)
    sde_build = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type_id", "blueprint_type_id"],
                name="industry_invention_outcome_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source_name} → {self.product_type_id} ({self.probability:.0%})"


class InventionDecryptor(models.Model):
    """A generic decryptor's effect on invention (SDE dogma 1112/1113/1114/1124)."""

    type_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    probability_multiplier = models.FloatField(default=1.0)
    runs_modifier = models.IntegerField(default=0)
    me_modifier = models.IntegerField(default=0)
    te_modifier = models.IntegerField(default=0)
    sde_build = models.IntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return str(self.name)
