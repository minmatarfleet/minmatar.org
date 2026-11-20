"""ESI health: scope changes and the Discord messages superusers send.

A scope added to a group (Basic, Director, ...) only reaches tokens granted
after the change. A ScopeRollout records the change and how hard to ask for
it: not at all, as a suggestion task, or as a required task (Director scopes
become a corporation task for CEOs and directors).

Pilots get no Discord message about ESI unless they turned task messages on,
except an EsiMessage a superuser sends by hand from Manage › ESI health.
"""

from django.contrib.auth.models import User
from django.db import models


class ScopeRollout(models.Model):
    MODE_NONE = "none"
    MODE_SUGGEST = "suggest"
    MODE_REQUIRE = "require"
    MODE_CHOICES = (
        (MODE_NONE, "Don't ask"),
        (MODE_SUGGEST, "Suggest"),
        (MODE_REQUIRE, "Require"),
    )

    scope = models.CharField(max_length=100, unique=True)
    # A TokenType value: "Basic", "Director", ...
    scope_group = models.CharField(max_length=40)
    # What uses it, as the screen names it: "structure search".
    label = models.CharField(max_length=100)
    added_on = models.DateField()
    mode = models.CharField(
        max_length=10, choices=MODE_CHOICES, default=MODE_NONE
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ("-added_on", "scope")

    def __str__(self):
        return f"{self.scope_group} · {self.scope} ({self.mode})"


class EsiMessage(models.Model):
    """One Discord DM a superuser sent a pilot about re-adding characters."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="esi_messages"
    )
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    # How many characters needed re-adding when it was sent.
    characters = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-sent_at",)
        indexes = [models.Index(fields=["user", "-sent_at"])]

    def __str__(self):
        return f"ESI message to {self.user_id} at {self.sent_at:%Y-%m-%d}"
