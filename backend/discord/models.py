"""Database models for Discord integration"""

import logging

import requests
from django.contrib.auth.models import Group, User
from django.db import models

from discord.client import DiscordClient

# Create your models here.
discord = DiscordClient()
logger = logging.getLogger(__name__)


class DiscordUser(models.Model):
    """Representation of an external Discord user"""

    id = models.BigIntegerField(primary_key=True)
    discord_tag = models.CharField(max_length=100)
    avatar = models.CharField(max_length=100, blank=True, null=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="discord_user"
    )
    nickname = models.CharField(max_length=100, blank=True, null=True)
    is_down_under = models.BooleanField(default=False)
    dress_wearer = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.discord_tag)


class DiscordRole(models.Model):
    """Representation of an external Discord role on a Discord server"""

    role_id = models.BigIntegerField(blank=True, unique=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(DiscordUser, related_name="groups")
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="discord_group"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self) -> str:
        return str(self.name)

    def delete(self, *args, **kwargs):
        if self.role_id:
            try:
                discord.delete_role(self.role_id)
            except requests.HTTPError as e:
                logger.warning(
                    "Could not delete Discord role %s (id=%s): %s",
                    self.name,
                    self.role_id,
                    e,
                )
        super().delete(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["role_id"]),
        ]


class DiscordChannelActivityRecord(models.Model):
    TEXT_MESSAGE = "text_message"
    VOICE_MINUTE = "voice_minute"

    ACTIVITY_TYPE_CHOICES = [
        (TEXT_MESSAGE, "Text message"),
        (VOICE_MINUTE, "Voice minute"),
    ]

    created_on = models.DateTimeField(auto_now_add=True)
    activity_type = models.CharField(
        max_length=32, choices=ACTIVITY_TYPE_CHOICES
    )
    username = models.CharField(max_length=255)
    quantity = models.IntegerField(
        help_text="Minutes for voice activity, message count for text activity."
    )
    channel_id = models.BigIntegerField(null=True, blank=True)
    channel_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_on"], name="created_on_idx"),
            models.Index(fields=["username"], name="username_idx"),
            models.Index(
                fields=["channel_id", "created_on"],
                name="channel_created_on_idx",
            ),
            models.Index(
                fields=["activity_type", "created_on"],
                name="activity_type_created_on_idx",
            ),
        ]


class DiscordGuild(models.Model):
    guild_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    is_primary = models.BooleanField(
        default=False,
        help_text="Matches DISCORD_GUILD_ID in application settings.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Bot was present in this guild on the last sync.",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    # From the last role snapshot. False until the bot has Manage Roles
    # (or Administrator) on this server. The reconciler skips it until then.
    # db_default keeps inserts from code that predates these columns working.
    can_manage_roles = models.BooleanField(default=False, db_default=False)
    # When the snapshot last finished, including a permission failure.
    # Empty while a connect is still waiting on Discord.
    roles_checked_at = models.DateTimeField(null=True, blank=True)
    # id, name, position, managed, assignable. Role ids are strings:
    # snowflakes do not fit in a JavaScript number.
    roles = models.JSONField(default=list, blank=True, db_default=[])
    # Who may stay on a corporation's server (discord.guild_access). Blank
    # means anyone. The bot only removes people with Kick Members, and only
    # after they have been on the pending list for member_grace_hours.
    MEMBER_POLICY_OFF = ""
    MEMBER_POLICY_CORPORATION = "corporation"
    MEMBER_POLICY_ALLIANCE = "alliance"
    MEMBER_POLICY_CHOICES = [
        (MEMBER_POLICY_OFF, "Anyone"),
        (MEMBER_POLICY_CORPORATION, "Corporation members only"),
        (MEMBER_POLICY_ALLIANCE, "Alliance members only"),
    ]
    member_policy = models.CharField(
        max_length=16,
        choices=MEMBER_POLICY_CHOICES,
        blank=True,
        default="",
        db_default="",
    )
    member_grace_hours = models.PositiveSmallIntegerField(
        default=24, db_default=24
    )
    # From the last role snapshot, like can_manage_roles.
    can_kick_members = models.BooleanField(default=False, db_default=False)
    members_checked_at = models.DateTimeField(null=True, blank=True)
    members_last_removed = models.PositiveIntegerField(default=0, db_default=0)
    # Set when one pass would remove more people than the safety limit.
    # Nobody is removed until a director approves; the approval covers
    # everyone flagged before it.
    members_held_at = models.DateTimeField(null=True, blank=True)
    members_held_count = models.PositiveIntegerField(default=0, db_default=0)
    members_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return str(self.name)


class DiscordRoleMapping(models.Model):
    """One existing Discord role standing in for a membership state.

    Corporation and tribe servers share this table. The alliance Discord
    and a Fishermen server are never mapped here. The reconciler only adds
    and removes these roles for linked accounts.
    """

    STATE_MEMBER = "member"
    STATE_DIRECTOR = "director"
    STATE_RECRUITER = "recruiter"
    STATE_STRUCTURE_MANAGER = "structure_manager"
    STATE_ALLIANCE_MEMBER = "alliance_member"
    STATE_CHOICES = [
        (STATE_MEMBER, "Member"),
        (STATE_DIRECTOR, "Director"),
        (STATE_RECRUITER, "Recruiter"),
        (STATE_STRUCTURE_MANAGER, "Structure manager"),
        (STATE_ALLIANCE_MEMBER, "Alliance member"),
    ]

    PROBLEM_MISSING = "missing"
    PROBLEM_ABOVE_BOT = "above_bot"

    guild = models.ForeignKey(
        DiscordGuild,
        on_delete=models.CASCADE,
        related_name="role_mappings",
    )
    state = models.CharField(max_length=32, choices=STATE_CHOICES)
    role_id = models.BigIntegerField()
    # missing: the role is gone. above_bot: the bot cannot assign it.
    problem = models.CharField(max_length=16, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["guild", "state"],
                name="discord_role_mapping_guild_state",
            ),
            models.UniqueConstraint(
                fields=["guild", "role_id"],
                name="discord_role_mapping_guild_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guild_id} {self.state} -> {self.role_id}"


class DiscordGuildExemption(models.Model):
    """A Discord username the member policy never removes.

    Matched on the username, and on the account id once the bot has seen
    them, so a rename doesn't drop the exemption.
    """

    guild = models.ForeignKey(
        DiscordGuild,
        on_delete=models.CASCADE,
        related_name="member_exemptions",
    )
    username = models.CharField(max_length=32)
    discord_id = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["username"]
        constraints = [
            models.UniqueConstraint(
                fields=["guild", "username"],
                name="discord_guild_exemption_username",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guild_id} {self.username}"


class DiscordGuildRemoval(models.Model):
    """Someone on a corporation's server who doesn't meet its member policy.

    They are removed once flagged_at is member_grace_hours old, and the row
    is dropped as soon as they qualify, leave, or are exempted.
    """

    REASON_UNLINKED = "unlinked"
    REASON_NOT_CORPORATION = "not_corporation"
    REASON_NOT_ALLIANCE = "not_alliance"
    REASON_CHOICES = [
        (REASON_UNLINKED, "No minmatar.org account"),
        (REASON_NOT_CORPORATION, "Not in the corporation"),
        (REASON_NOT_ALLIANCE, "Not in the alliance"),
    ]

    guild = models.ForeignKey(
        DiscordGuild,
        on_delete=models.CASCADE,
        related_name="member_removals",
    )
    discord_id = models.BigIntegerField()
    username = models.CharField(max_length=32, blank=True, default="")
    display_name = models.CharField(max_length=100, blank=True, default="")
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    flagged_at = models.DateTimeField()

    class Meta:
        ordering = ["flagged_at", "discord_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["guild", "discord_id"],
                name="discord_guild_removal_member",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guild_id} {self.username or self.discord_id}"


class DiscordChannel(models.Model):
    TEXT = "text"
    VOICE = "voice"
    STAGE = "stage"
    FORUM = "forum"
    CATEGORY = "category"
    UNKNOWN = "unknown"

    CHANNEL_TYPE_CHOICES = [
        (TEXT, "Text"),
        (VOICE, "Voice"),
        (STAGE, "Stage"),
        (FORUM, "Forum"),
        (CATEGORY, "Category"),
        (UNKNOWN, "Unknown"),
    ]

    channel_id = models.BigIntegerField(unique=True)
    guild = models.ForeignKey(
        DiscordGuild,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    name = models.CharField(max_length=255)
    channel_type = models.CharField(
        max_length=32, choices=CHANNEL_TYPE_CHOICES
    )
    track_voice_activity = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, the bot records voice presence in this channel each minute."
        ),
    )
    receive_capital_pings = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, capital kills within 8 LY of Amamake are posted here."
        ),
    )
    receive_amarr_fleet_pings = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, Amarr fleet_active feed events are posted here."
        ),
    )
    receive_lp_buyback = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, LP buyback order threads are created in this "
            "forum. Only one channel should have this enabled."
        ),
    )
    receive_buyback = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, hangar buyback purchase-order threads are created "
            "in this forum. Only one channel should have this enabled."
        ),
    )
    receive_lp_conversion_alerts = models.BooleanField(
        default=False,
        db_default=False,
        help_text=(
            "When enabled, the Conversion Team is told here about LP buyback "
            "orders left open for a week. Only one channel should have this "
            "enabled."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.receive_lp_buyback:
            type(self).objects.filter(receive_lp_buyback=True).exclude(
                pk=self.pk
            ).update(receive_lp_buyback=False)
        if self.receive_buyback:
            type(self).objects.filter(receive_buyback=True).exclude(
                pk=self.pk
            ).update(receive_buyback=False)
        if self.receive_lp_conversion_alerts:
            type(self).objects.filter(
                receive_lp_conversion_alerts=True
            ).exclude(pk=self.pk).update(receive_lp_conversion_alerts=False)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_channel_type_display()})"
