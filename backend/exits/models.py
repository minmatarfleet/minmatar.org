"""Pilots leaving tracked corporations, and what their CEO said about it.

See docs/exits/exit-flow-design.md. Departures are keyed by character ID so
they work for pilots with no site account; ``user`` is filled in when known.
"""

from django.contrib.auth.models import User
from django.db import models

from eveonline.models import EveCorporation

STATUS_PENDING = "pending"
STATUS_DROPPED = "dropped"
STATUS_CONFIRMED = "confirmed"

KIND_EXIT = "exit"
KIND_ALLIANCE_MOVE = "alliance_move"

REASON_KICKED_INACTIVE = "kicked_inactive"
REASON_KICKED_OTHER = "kicked_other"
REASON_LEFT = "left"


class MemberSnapshot(models.Model):
    """The last member list seen for a tracked corporation."""

    corporation = models.OneToOneField(
        EveCorporation,
        on_delete=models.CASCADE,
        related_name="member_snapshot",
    )
    member_ids = models.JSONField(default=list)
    alliance_id = models.BigIntegerField(null=True, blank=True)
    taken_at = models.DateTimeField()

    def __str__(self):
        return f"{self.corporation} ({len(self.member_ids)} members)"


class Departure(models.Model):
    """A character missing from a tracked corporation's member list."""

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_DROPPED, "Dropped"),
        (STATUS_CONFIRMED, "Confirmed"),
    )
    KIND_CHOICES = (
        ("", "Not known yet"),
        (KIND_EXIT, "Exit"),
        (KIND_ALLIANCE_MOVE, "Alliance move"),
    )
    REASON_CHOICES = (
        ("", "Not answered"),
        (REASON_KICKED_INACTIVE, "Kicked for inactivity"),
        (REASON_KICKED_OTHER, "Kicked for another reason"),
        (REASON_LEFT, "Left on their own"),
    )

    corporation = models.ForeignKey(
        EveCorporation, on_delete=models.CASCADE, related_name="departures"
    )
    character_id = models.BigIntegerField(db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departures",
    )
    first_missing_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    destination_corporation_id = models.BigIntegerField(null=True, blank=True)
    kind = models.CharField(
        max_length=16, choices=KIND_CHOICES, default="", blank=True
    )
    destination_is_npc = models.BooleanField(default=False)
    reason = models.CharField(
        max_length=16, choices=REASON_CHOICES, default="", blank=True
    )
    can_rejoin = models.BooleanField(null=True, blank=True)
    note = models.TextField(blank=True)
    answered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departures_answered",
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    survey_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["corporation", "status"])]

    def __str__(self):
        return f"{self.character_id} left {self.corporation} ({self.status})"


class RejoinFlag(models.Model):
    """A CEO's "can't rejoin" answer, seen by every alliance corporation's recruiters.

    Keyed by character ID; ``user`` widens it to every character on the
    account, alts added later included. Active while ``cleared_at`` is null.
    """

    character_id = models.BigIntegerField(db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejoin_flags",
    )
    departure = models.ForeignKey(
        Departure, on_delete=models.CASCADE, related_name="flags"
    )
    corporation = models.ForeignKey(
        EveCorporation, on_delete=models.CASCADE, related_name="rejoin_flags"
    )
    note = models.TextField()
    set_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rejoin_flags_set",
    )
    set_at = models.DateTimeField()
    cleared_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejoin_flags_cleared",
    )
    cleared_at = models.DateTimeField(null=True, blank=True)

    @property
    def active(self) -> bool:
        return self.cleared_at is None

    def __str__(self):
        return f"{self.character_id} can't rejoin ({self.corporation})"


class FlagAcceptance(models.Model):
    """A recruiter accepted an applicant despite active can't-rejoin flags."""

    application = models.ForeignKey(
        "applications.EveCorporationApplication",
        on_delete=models.CASCADE,
        related_name="flag_acceptances",
    )
    flag_ids = models.JSONField(default=list)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    accepted_at = models.DateTimeField()

    def __str__(self):
        return (
            f"Application {self.application_id} accepted over {self.flag_ids}"
        )


class RecruiterAlert(models.Model):
    """One alert in the recruiter alerts channel (design 06).

    At most one per application, corporation and reason: a transfer is a new
    application for the receiving corporation, and a later flag can follow a
    "kicked for another reason" alert once.
    """

    REASON_FLAG = "flag"
    REASON_KICKED_OTHER = "kicked_other"
    REASON_CHOICES = (
        (REASON_FLAG, "Can't-rejoin flag"),
        (REASON_KICKED_OTHER, "Kicked for another reason"),
    )

    application = models.ForeignKey(
        "applications.EveCorporationApplication",
        on_delete=models.CASCADE,
        related_name="recruiter_alerts",
    )
    corporation_id = models.BigIntegerField()
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    sent_at = models.DateTimeField()
    message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["application", "corporation_id", "reason"],
                name="exits_one_alert_per_application_reason",
            )
        ]

    def __str__(self):
        return f"Alert {self.reason} for application {self.application_id}"
