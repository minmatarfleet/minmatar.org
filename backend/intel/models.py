import secrets

from django.contrib.auth.models import User
from django.db import models


def new_public_id() -> str:
    return secrets.token_urlsafe(8)


class IntelReport(models.Model):
    """A d-scan or Local list a pilot shared to the alliance intel sheet."""

    class Kind(models.TextChoices):
        DSCAN = "dscan", "D-scan"
        LOCAL = "local", "Local"

    # Shared links use this, not the row id, so reports can't be walked.
    public_id = models.CharField(
        max_length=16, unique=True, default=new_public_id, editable=False
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    solar_system_id = models.BigIntegerField(null=True, blank=True)
    system_name = models.CharField(max_length=64, blank=True, default="")
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intel_reports",
    )
    reporter_name = models.CharField(max_length=64, blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")
    raw = models.TextField()
    # The parsed breakdown (services.ships.summarize_dscan /
    # services.local.summarize_local), computed once when shared.
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["solar_system_id", "kind", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.system_name} {self.public_id}"


class IntelEntity(models.Model):
    """An alliance, corporation or character the affiliation database knows.

    Groups (alliances, and corporations outside an alliance) are queued for
    an investigation of their kill history when we keep seeing them.
    Characters only get a row once they have an affiliation to record.
    """

    class Kind(models.TextChoices):
        ALLIANCE = "alliance", "Alliance"
        CORPORATION = "corporation", "Corporation"
        CHARACTER = "character", "Character"

    class Status(models.TextChoices):
        NEW = "new", "New"
        QUEUED = "queued", "Queued"
        INVESTIGATING = "investigating", "Investigating"
        DONE = "done", "Investigated"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    eve_id = models.BigIntegerField()
    name = models.CharField(max_length=128, blank=True, default="")
    # Times we saw the group in the feed or a Local report (see
    # intel.affiliations.sightings); orders the investigation queue.
    sightings = models.PositiveIntegerField(default=0)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.NEW
    )
    # Higher runs first; "Investigate now" and a strong partner of a
    # finished investigation raise it.
    priority = models.IntegerField(default=0)
    queued_at = models.DateTimeField(null=True, blank=True)
    investigated_at = models.DateTimeField(null=True, blank=True)
    # The militia most of its sampled kills were flown in, if any.
    faction_id = models.IntegerField(null=True, blank=True)
    # Corporations: ESI alliance history, newest first, as
    # [{"alliance_id", "start_date"}].
    alliance_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "eve_id"], name="intel_entity_kind_eve_id"
            )
        ]
        indexes = [
            models.Index(fields=["status", "-priority", "-sightings"]),
            models.Index(fields=["eve_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.name or self.eve_id}"


class IntelSampleMonth(models.Model):
    """How much of one group's month an investigation sampled."""

    entity = models.ForeignKey(
        IntelEntity, on_delete=models.CASCADE, related_name="sample_months"
    )
    month = models.DateField()  # the 1st
    kills = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    # A month that had ended when it was sampled is never fetched again.
    complete = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "month"], name="intel_sample_month_unique"
            )
        ]


class IntelCoAttack(models.Model):
    """Evidence for one month: who was on a group's kills and losses.

    ``shared`` counts the group's sampled kills the partner was also on,
    ``militia_shared`` the ones where both flew for the same militia, and
    ``against`` the group's sampled losses the partner shot. A character
    partner is someone outside the group; ``partner_group`` is the alliance
    or corporation they flew for on their last shared kill.
    """

    entity = models.ForeignKey(
        IntelEntity, on_delete=models.CASCADE, related_name="co_attacks"
    )
    month = models.DateField()
    partner_kind = models.CharField(
        max_length=16, choices=IntelEntity.Kind.choices
    )
    partner_id = models.BigIntegerField()
    partner_group = models.BigIntegerField(null=True, blank=True)
    shared = models.PositiveIntegerField(default=0)
    militia_shared = models.PositiveIntegerField(default=0)
    against = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "month", "partner_kind", "partner_id"],
                name="intel_co_attack_unique",
            )
        ]
        indexes = [
            models.Index(fields=["partner_kind", "partner_id"]),
        ]


class IntelBloc(models.Model):
    """A real-world group, named by us: an alliance and everyone it runs.

    The anchor is the group the bloc is named after; it belongs to the bloc
    without an affiliation row. A bloc scoring made shows in the tools once
    it has a live affiliation; one the intel team made always does.
    """

    name = models.CharField(max_length=128)
    anchor = models.OneToOneField(
        IntelEntity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anchored_bloc",
    )
    notes = models.TextField(blank=True, default="")
    manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return str(self.name)


class IntelAffiliation(models.Model):
    """Who really belongs to a bloc, and how sure we are.

    Inferred rows are suggestions until someone on the intel team confirms
    or rejects them. A rejection sticks: scoring never suggests it again.
    ``last_month`` is the last month with evidence; an inferred row with
    none for six months is marked ended (a former pet or associate).
    """

    class Relation(models.TextChoices):
        PET = "pet", "Pet"
        ALT = "alt", "Alt alliance"
        ALLY = "ally", "Ally"
        ASSOCIATE = "associate", "Associate"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class Source(models.TextChoices):
        INFERRED = "inferred", "Inferred"
        MANUAL = "manual", "Manual"

    entity = models.ForeignKey(
        IntelEntity, on_delete=models.CASCADE, related_name="affiliations"
    )
    bloc = models.ForeignKey(
        IntelBloc, on_delete=models.CASCADE, related_name="affiliations"
    )
    relation = models.CharField(max_length=16, choices=Relation.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUGGESTED
    )
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.INFERRED
    )
    confidence = models.FloatField(default=0)
    # What the scorer saw: shares, months together, kills against, the
    # partner it leans on, alliance history. Shown as the "why".
    evidence = models.JSONField(default=dict, blank=True)
    first_month = models.DateField(null=True, blank=True)
    last_month = models.DateField(null=True, blank=True)
    ended = models.BooleanField(default=False)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "bloc"], name="intel_affiliation_unique"
            )
        ]
        indexes = [models.Index(fields=["status", "-confidence"])]

    def __str__(self) -> str:
        return f"{self.entity} → {self.bloc} ({self.relation})"
