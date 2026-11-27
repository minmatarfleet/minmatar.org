from django.contrib.auth.models import User
from django.db import models


class TribeGroupCorporationFollow(models.Model):
    """A corporation's copy of a tribe group's fleet posts in its own
    Discord server: the roundup, the quiet pre-ping and the start ping.

    The corporation's CEO or a director asks; it forwards only once one of
    the group's managers approved it (docs/tribes/group-fleet-roundup.md).
    """

    STATUS_REQUESTED = "requested"
    STATUS_APPROVED = "approved"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Waiting for approval"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REVOKED, "Revoked"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="corporation_follows",
    )
    corporation = models.ForeignKey(
        "eveonline.EveCorporation",
        on_delete=models.CASCADE,
        related_name="group_follows",
    )
    channel_id = models.BigIntegerField(
        help_text="Channel in the corporation's linked Discord server."
    )
    channel_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
        db_default=STATUS_REQUESTED,
    )
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    # The last forwarded post: None until one was sent.
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    last_delivery_ok = models.BooleanField(null=True, blank=True)
    # unknown_channel, missing_access, missing_permissions or error.
    last_delivery_error = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "corporation"],
                name="unique_tribe_group_corporation_follow",
            )
        ]

    def __str__(self) -> str:
        return f"{self.corporation} follows {self.tribe_group}"

    def is_forwarding(self) -> bool:
        """Approved, and the corporation's bot is still in its server."""
        # pylint: disable-next=import-outside-toplevel
        from eveonline.models import EveCorporation

        corporation = self.corporation
        return (
            self.status == self.STATUS_APPROVED
            and corporation.discord_guild_id is not None
            and corporation.discord_bot_status == EveCorporation.DISCORD_BOT_OK
        )
