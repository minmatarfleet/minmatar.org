"""Create the Fanfest tribe, led by Sycamoria when that pilot exists.

The chief is looked up by character name at migration time, so no user id
is hardcoded. When the name matches no pilot, or more than one account,
the tribe is created without a chief (the alliance executor stands in until
one is appointed). Re-running leaves an existing tribe untouched, except that
a still-empty chief seat is filled.

The tribe and group get auth groups ("Tribe - Fanfest" and
"Tribe Group - Fanfest Attendees"). They are created with the real Group
model so the discord signals create the matching Discord roles. If Discord
cannot be reached, that group is skipped and the deploy carries on; link it
in the admin later. Discord channels are never created automatically; set
discord_channel_id in the admin if one is wanted.
"""

import logging

from django.conf import settings
from django.db import migrations, transaction

logger = logging.getLogger(__name__)

TRIBE_SLUG = "fanfest"
GROUP_CODE = "fanfest.attendees"
CHIEF_CHARACTER_NAME = "Sycamoria"
TRIBE_AUTH_GROUP = "Tribe - Fanfest"
GROUP_AUTH_GROUP = "Tribe Group - Fanfest Attendees"


def ensure_auth_group_id(name):
    """Create (or reuse) an auth group and return its id, or None.

    Uses the real Group model, not the historical one, so the discord
    group_post_save signal fires and creates the Discord role. A Discord
    failure rolls back only this savepoint.
    """
    # pylint: disable-next=import-outside-toplevel
    from django.contrib.auth.models import Group  # noqa: PLC0415

    try:
        with transaction.atomic():
            group, _ = Group.objects.get_or_create(name=name)
            return group.id
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Could not create auth group %s", name)
        return None


def find_chief_id(apps):
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    User = apps.get_model("auth", "User")
    user_ids = set(
        EveCharacter.objects.filter(
            character_name__iexact=CHIEF_CHARACTER_NAME,
            user__isnull=False,
        ).values_list("user_id", flat=True)
    )
    if len(user_ids) != 1:
        return None
    user_id = user_ids.pop()
    return user_id if User.objects.filter(pk=user_id).exists() else None


def create_fanfest_tribe(apps, schema_editor):
    # Test databases stay empty; tests call seed_fanfest_tribe.
    if getattr(settings, "TESTING", False):
        return
    seed_fanfest_tribe(apps, auth_group_id=ensure_auth_group_id)


def seed_fanfest_tribe(apps, auth_group_id=None):
    """Create the tribe and group. auth_group_id(name) -> id links roles."""
    Tribe = apps.get_model("tribes", "Tribe")
    TribeGroup = apps.get_model("tribes", "TribeGroup")

    chief_id = find_chief_id(apps)

    tribe = Tribe.objects.filter(slug=TRIBE_SLUG).first()
    if tribe is None:
        tribe = Tribe.objects.create(
            slug=TRIBE_SLUG,
            name="Fanfest",
            description=(
                "Flying out to EVE Fanfest? Meet the pilots going, plan "
                "the trip together, and represent the alliance."
            ),
            chief_id=chief_id,
            is_active=True,
        )
    elif tribe.chief_id is None and chief_id is not None:
        tribe.chief_id = chief_id
        tribe.save(update_fields=["chief"])

    group = TribeGroup.objects.filter(code=GROUP_CODE).first()
    if group is None:
        group = TribeGroup.objects.create(
            tribe=tribe,
            name="Attendees",
            code=GROUP_CODE,
            description="Pilots attending or helping organise EVE Fanfest.",
            is_active=True,
        )

    if auth_group_id is None:
        return
    for row, name in ((tribe, TRIBE_AUTH_GROUP), (group, GROUP_AUTH_GROUP)):
        if row.group_id is not None:
            continue
        group_id = auth_group_id(name)
        if group_id is not None:
            row.group_id = group_id
            row.save(update_fields=["group"])


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0049_tribe_discord_guild"),
        ("eveonline", "0111_evelocation_freight_active_help_text"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # Irreversible by design: members may have joined by then.
        migrations.RunPython(create_fanfest_tribe, migrations.RunPython.noop),
    ]
