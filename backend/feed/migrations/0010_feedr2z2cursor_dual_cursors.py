from django.db import migrations, models


def copy_last_to_catchup(apps, schema_editor):
    FeedR2z2Cursor = apps.get_model("feed", "FeedR2z2Cursor")
    for cursor in FeedR2z2Cursor.objects.all():
        cursor.catchup_sequence_id = cursor.last_sequence_id
        # live stays 0 until first poll seeds from sequence.json
        cursor.live_sequence_id = 0
        cursor.save(update_fields=["catchup_sequence_id", "live_sequence_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("feed", "0009_feed_capital_ping"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedr2z2cursor",
            name="live_sequence_id",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="feedr2z2cursor",
            name="catchup_sequence_id",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="feedr2z2cursor",
            name="paused_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feedr2z2cursor",
            name="live_idle_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feedr2z2cursor",
            name="last_request_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(copy_last_to_catchup, migrations.RunPython.noop),
    ]
