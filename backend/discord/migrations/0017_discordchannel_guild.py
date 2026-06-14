from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_discord_channel_guild(apps, schema_editor):
    discord_guild = apps.get_model("discord", "DiscordGuild")
    discord_channel = apps.get_model("discord", "DiscordChannel")

    primary_guild, _ = discord_guild.objects.get_or_create(
        guild_id=settings.DISCORD_GUILD_ID,
        defaults={
            "name": "Primary guild",
            "is_primary": True,
            "is_active": True,
        },
    )
    discord_channel.objects.filter(guild__isnull=True).update(
        guild=primary_guild
    )


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0016_discordguild"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordchannel",
            name="guild",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="channels",
                to="discord.discordguild",
            ),
        ),
        migrations.RunPython(
            backfill_discord_channel_guild,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="discordchannel",
            name="guild",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="channels",
                to="discord.discordguild",
            ),
        ),
    ]
