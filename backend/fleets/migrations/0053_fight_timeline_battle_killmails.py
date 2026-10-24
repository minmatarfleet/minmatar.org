"""Snapshot every killmail around a fleet's rounds for the battle report."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0052_rename_warzone_pings_audience"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefleetfighttimeline",
            name="battle_killmails",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="evefleetfighttimeline",
            name="battle_names",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="evefleetfighttimeline",
            name="battle_collected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
