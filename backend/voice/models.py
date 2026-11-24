"""Fleet voice on Mumble: who may connect, and with what rights.

Django decides; the voice service (top-level ``voice/``) obeys. Access is
worked out in ``voice.access`` and published to Redis by
``voice.publisher``. See docs/mumble-architecture.md.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from fleets.models import EveFleet

BRANCH_COUNT = 3
MAX_CERTIFICATES = 3


class VoiceIdentity(models.Model):
    """A character that signed in on /voice. Its id is the Mumble user id."""

    character_id = models.BigIntegerField(unique=True)
    character_name = models.CharField(max_length=255)
    # EVE's owner hash: it changes when the character is sold.
    owner_hash = models.CharField(max_length=255, blank=True, default="")
    # Public affiliation at sign-in, for campaign allies without an account.
    corporation_id = models.BigIntegerField(null=True, blank=True)
    alliance_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.character_name} ({self.character_id})"


class VoiceCertificate(models.Model):
    """A Mumble client certificate bound to an identity on first connect."""

    identity = models.ForeignKey(
        VoiceIdentity, on_delete=models.CASCADE, related_name="certificates"
    )
    cert_hash = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.identity_id}: {str(self.cert_hash)[:12]}"


class VoiceGrant(models.Model):
    """Fleet-scoped access, stored so logins never join fleet tables.

    Campaign allies are not stored: ``voice.access`` matches them on read
    from the campaign's parties, since a corporation or alliance entry can't
    be listed per character.
    """

    SOURCE_IN_FLEET = "in_fleet"
    SOURCE_VOLUNTEER = "volunteer"
    SOURCE_INVITE = "invite"
    SOURCE_CREATOR = "creator"
    SOURCE_BOSS = "boss"
    SOURCE_CO_FC = "co_fc"
    SOURCE_CAPITAL = "capital"
    SOURCE_CHOICES = (
        (SOURCE_IN_FLEET, "In the in-game fleet"),
        (SOURCE_VOLUNTEER, "Volunteered"),
        (SOURCE_INVITE, "Said in to an invite"),
        (SOURCE_CREATOR, "Fleet creator"),
        (SOURCE_BOSS, "In-game fleet boss"),
        (SOURCE_CO_FC, "Co-FC"),
        (SOURCE_CAPITAL, "Capital pilot"),
    )
    # Sources that make the pilot part of the fleet (placement picks it).
    PART_OF_FLEET = frozenset(
        {
            SOURCE_IN_FLEET,
            SOURCE_VOLUNTEER,
            SOURCE_CREATOR,
            SOURCE_BOSS,
            SOURCE_CO_FC,
        }
    )

    ROLE_MEMBER = "member"
    ROLE_COMMANDER = "commander"
    ROLE_CAPITAL = "capital"
    ROLE_CHOICES = (
        (ROLE_MEMBER, "Member"),
        (ROLE_COMMANDER, "Commander"),
        (ROLE_CAPITAL, "Capital"),
    )

    character_id = models.BigIntegerField(db_index=True)
    fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="voice_grants"
    )
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    role = models.CharField(
        max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER
    )
    # Logistics hull flown or volunteered (placement goes to Logistics).
    logistics = models.BooleanField(default=False)
    wing_id = models.BigIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character_id", "fleet", "source", "role"],
                name="voice_grant_unique_source",
            )
        ]

    def __str__(self):
        return (
            f"{self.character_id} {self.source}/{self.role} on {self.fleet_id}"
        )


class VoiceBan(models.Model):
    """Refuses everything for a character. Checked before any access."""

    character_id = models.BigIntegerField(db_index=True)
    character_name = models.CharField(max_length=255, blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    lifted_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def active(cls, now=None):
        now = now or timezone.now()
        return cls.objects.filter(lifted_at__isnull=True).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )

    def __str__(self):
        return f"ban {self.character_id}"


class VoiceConnectToken(models.Model):
    """One-time Mumble password: hashed, 2 minutes, bound to the identity."""

    identity = models.ForeignKey(
        VoiceIdentity, on_delete=models.CASCADE, related_name="tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class VoiceAuditEvent(models.Model):
    """What happened on voice. Kept forever; never stores IP addresses."""

    KIND_SIGN_IN = "sign_in"
    KIND_CONNECT_TOKEN = "connect_token"
    KIND_CERT_BOUND = "cert_bound"
    KIND_CERT_REVOKED = "cert_revoked"
    KIND_OWNER_CHANGED = "owner_changed"
    KIND_CO_FC = "co_fc"
    KIND_KICK = "kick"
    KIND_BAN = "ban"
    KIND_LEASE = "lease"
    KIND_RELEASE = "release"
    KIND_WINGS = "wings"

    kind = models.CharField(max_length=32, db_index=True)
    character_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    fleet_id = models.BigIntegerField(null=True, blank=True)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @classmethod
    def record(
        cls, kind, *, character_id=None, fleet_id=None, actor=None, **detail
    ):
        return cls.objects.create(
            kind=kind,
            character_id=character_id,
            fleet_id=fleet_id,
            actor=actor if getattr(actor, "pk", None) else None,
            detail=detail,
        )


class VoiceChannelLease(models.Model):
    """A Mumble fleet holding one of the three fleet branches."""

    branch = models.PositiveSmallIntegerField()
    fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="voice_leases"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    # Set when the fleet closes: the lease ends 30 minutes later.
    release_after = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    # FC's optional in-game wing -> channel name mapping.
    wing_channels = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch"],
                condition=models.Q(released_at__isnull=True),
                name="voice_one_active_lease_per_branch",
            ),
            models.UniqueConstraint(
                fields=["fleet"],
                condition=models.Q(released_at__isnull=True),
                name="voice_one_active_lease_per_fleet",
            ),
        ]

    @classmethod
    def active(cls):
        return cls.objects.filter(released_at__isnull=True)

    def __str__(self):
        return f"Fleet {self.branch} -> {self.fleet_id}"
