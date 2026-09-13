"""Seed the Pulse / Fishermen secondary Discord guild binding."""

from django.db import migrations

# Keep in sync with tribes.helpers.external_guild fishermen constants.
FISHERMEN_GROUP_CODE = "pulse.fishermen"
FISHERMEN_GUILD_ID = 834087499658952735
FISHERMEN_MEMBER_ROLE_ID = 1543301902375329922
FISHERMEN_ALERT_CHANNEL_ID = 1543302547157286972


def seed_fishermen_binding(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeExternalGuild = apps.get_model("tribes", "TribeExternalGuild")
    DiscordGuild = apps.get_model("discord", "DiscordGuild")
    group = TribeGroup.objects.filter(code=FISHERMEN_GROUP_CODE).first()
    guild = DiscordGuild.objects.filter(guild_id=FISHERMEN_GUILD_ID).first()
    if group is None or guild is None:
        return
    TribeExternalGuild.objects.get_or_create(
        tribe_group=group,
        defaults={
            "guild": guild,
            "member_role_id": FISHERMEN_MEMBER_ROLE_ID,
            "alert_channel_id": FISHERMEN_ALERT_CHANNEL_ID,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0037_remove_stale_celery_beat_tasks"),
        ("discord", "0016_discordguild"),
    ]

    operations = [
        migrations.RunPython(
            seed_fishermen_binding,
            migrations.RunPython.noop,
        ),
    ]
