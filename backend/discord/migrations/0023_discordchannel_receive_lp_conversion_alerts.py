# Conversion Team alert channel for stale LP buyback orders

from django.db import migrations, models

MINMATAR_GUILD_ID = 1041384161505722368
CONVERSION_CHANNEL_ID = 1174103016161427556


def register_conversion_channel(apps, schema_editor):
    """Point alerts at #conversion where the alliance guild is synced."""
    guild_model = apps.get_model("discord", "DiscordGuild")
    channel_model = apps.get_model("discord", "DiscordChannel")
    guild = guild_model.objects.filter(guild_id=MINMATAR_GUILD_ID).first()
    if guild is None:
        return
    if channel_model.objects.filter(
        receive_lp_conversion_alerts=True
    ).exists():
        return
    channel, created = channel_model.objects.get_or_create(
        channel_id=CONVERSION_CHANNEL_ID,
        defaults={
            "guild": guild,
            "name": "conversion",
            "channel_type": "text",
            "receive_lp_conversion_alerts": True,
        },
    )
    if not created:
        channel.receive_lp_conversion_alerts = True
        channel.save(update_fields=["receive_lp_conversion_alerts"])


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0022_discordchannel_receive_buyback"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordchannel",
            name="receive_lp_conversion_alerts",
            field=models.BooleanField(
                default=False,
                db_default=False,
                help_text=(
                    "When enabled, the Conversion Team is told here about LP "
                    "buyback orders left open for a week. Only one channel "
                    "should have this enabled."
                ),
            ),
        ),
        migrations.RunPython(
            register_conversion_channel, migrations.RunPython.noop
        ),
    ]
