# Generated for tribe catalog report bindings (phase 3)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0022_fleet_commanders_tribe_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribegroupactivityrecord",
            name="occurred_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the source event happened; falls back to created_at for metrics.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="tribegroupactivityrecord",
            index=models.Index(
                fields=["tribe_group_activity", "occurred_at"],
                name="tribes_tgarecord_act_occurred",
            ),
        ),
    ]
