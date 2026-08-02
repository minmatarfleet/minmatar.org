"""Shared helpers for Discord-related Django tests."""

from django.contrib.auth.models import Group, User
from django.db.models import signals

from discord.models import DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)


def reconnect_discord_group_signals() -> None:
    """
    Re-attach Discord group sync signals after tests that disconnect them.

    Idempotent via dispatch_uid. Use in setUp/tearDown so fail-closed cases
    still exercise m2m sync after other suites mute the signals.
    """
    signals.post_save.connect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )
    signals.pre_save.connect(
        resolve_existing_discord_role_from_server,
        sender=DiscordRole,
        dispatch_uid="resolve_existing_discord_role_from_server",
    )
    signals.m2m_changed.connect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
