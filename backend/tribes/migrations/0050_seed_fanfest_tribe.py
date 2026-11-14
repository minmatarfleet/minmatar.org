"""Create the Fanfest tribe, led by Sycamoria when that pilot exists.

The chief is looked up by character name at migration time, so no user id
is hardcoded. When the name matches no pilot, or more than one account,
the tribe is created without a chief (the alliance executor stands in until
one is appointed). Re-running leaves an existing tribe untouched, except that
a still-empty chief seat is filled.

The tribe's Discord role and channel are not created here; link them by hand
in the admin (Tribe.group and Tribe.discord_channel_id).
"""

from django.conf import settings
from django.db import migrations

TRIBE_SLUG = "fanfest"
GROUP_CODE = "fanfest.attendees"
CHIEF_CHARACTER_NAME = "Sycamoria"


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
    seed_fanfest_tribe(apps)


def seed_fanfest_tribe(apps):
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

    if not TribeGroup.objects.filter(code=GROUP_CODE).exists():
        TribeGroup.objects.create(
            tribe=tribe,
            name="Attendees",
            code=GROUP_CODE,
            description="Pilots attending or helping organise EVE Fanfest.",
            is_active=True,
        )


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
