"""Shared setup for tribe publishing tests (fleets, posts, events)."""

from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals

import factory

from discord.models import DiscordRole
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

ROLE_ID = 777000111
TRIBE_CHANNEL_ID = 555000111
GROUP_CHANNEL_ID = 555000222

_next_character_id = [91000000]


def make_tribe_group(
    name="Dreads",
    code="capitals.dreads",
    *,
    tribe=None,
    group_channel_id=GROUP_CHANNEL_ID,
    role_id=ROLE_ID,
    **fields,
) -> TribeGroup:
    """A group with a Discord role and channel, in a Capitals tribe."""
    if tribe is None:
        tribe, _ = Tribe.objects.get_or_create(
            slug="capitals",
            defaults={
                "name": "Capitals",
                "discord_channel_id": TRIBE_CHANNEL_ID,
            },
        )
    auth_group = None
    if role_id:
        with factory.django.mute_signals(signals.post_save):
            auth_group = Group.objects.create(name=f"Tribe Group - {name}")
        DiscordRole.objects.create(
            role_id=role_id, name=auth_group.name, group=auth_group
        )
    return TribeGroup.objects.create(
        tribe=tribe,
        name=name,
        code=code,
        group=auth_group,
        discord_channel_id=group_channel_id,
        **fields,
    )


def make_user(username, *, perms=(), character_name=None) -> User:
    """A user with a primary character and the given permission codenames."""
    user = User.objects.create_user(username=username)
    for codename in perms:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    _next_character_id[0] += 1
    with factory.django.mute_signals(signals.post_save, signals.pre_save):
        character = EveCharacter.objects.create(
            character_id=_next_character_id[0],
            character_name=character_name or f"{username} pilot",
            user=user,
        )
        set_primary_character(user, character)
    return user


def add_member(group, user, status=TribeGroupMembership.STATUS_ACTIVE):
    """A membership; Discord role syncing is muted."""
    with factory.django.mute_signals(signals.m2m_changed):
        return TribeGroupMembership.objects.create(
            user=user, tribe_group=group, status=status
        )
