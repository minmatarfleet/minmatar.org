"""Industry job model: tracks character industry jobs from ESI."""

from django.db import models


class IndustryJob(models.Model):
    """
    An industry job (manufacturing, research, etc.) for a character.
    Synced from ESI; job_id is the ESI job identifier.
    """

    job_id = models.BigIntegerField(unique=True, db_index=True)
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="industry_jobs",
    )

    # Job type and blueprint
    activity_id = models.IntegerField(
        help_text="Activity: 1=Manufacturing, 2=Researching TE, 3=Researching ME, etc."
    )
    blueprint_id = models.BigIntegerField()
    blueprint_type_id = models.IntegerField(db_index=True)

    # Locations (IDs from ESI; may not exist in EveLocation)
    blueprint_location_id = models.BigIntegerField()
    facility_id = models.BigIntegerField()
    location_id = models.BigIntegerField(db_index=True)
    output_location_id = models.BigIntegerField()

    # Status and timing
    status = models.CharField(max_length=32, db_index=True)
    installer_id = models.BigIntegerField(
        help_text="Character ID that installed the job."
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration = models.PositiveIntegerField(help_text="Duration in seconds.")
    completed_date = models.DateTimeField(null=True, blank=True)
    completed_character_id = models.BigIntegerField(null=True, blank=True)

    # Job params
    runs = models.PositiveIntegerField()
    licensed_runs = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )

    # When we last saw this job from ESI
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-end_date"]
        indexes = [
            models.Index(fields=["character", "status"]),
        ]

    def __str__(self):
        return f"Job {self.job_id} ({self.character.character_name}, {self.status})"
