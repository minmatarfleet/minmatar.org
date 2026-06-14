from django.db import migrations, models

LEGACY_STANDING_FLEET_CHANNEL_ID = 1306515072650313728


def backfill_legacy_channel_id(apps, schema_editor):
    record_model = apps.get_model("discord", "DiscordVoiceMinuteRecord")
    record_model.objects.filter(channel_id__isnull=True).update(
        channel_id=LEGACY_STANDING_FLEET_CHANNEL_ID
    )


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0012_discordvoiceminuterecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordvoiceminuterecord",
            name="channel_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discordvoiceminuterecord",
            name="channel_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(
            backfill_legacy_channel_id,
            migrations.RunPython.noop,
        ),
        migrations.AlterModelTable(
            name="discordvoiceminuterecord",
            table="discord_discordvoiceminuterecord",
        ),
        migrations.AddIndex(
            model_name="discordvoiceminuterecord",
            index=models.Index(
                fields=["channel_id", "created_on"],
                name="channel_created_on_idx",
            ),
        ),
    ]
