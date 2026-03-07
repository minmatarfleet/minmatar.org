# Generated manually for point weights on TribeGroupActivity

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0019_tribegroupactivity_tribegroupactivityrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribegroupactivity",
            name="points_per_record",
            field=models.FloatField(
                blank=True,
                help_text="Points awarded per record (count-based: killmail, fleet).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tribegroupactivity",
            name="points_per_unit",
            field=models.FloatField(
                blank=True,
                help_text="Points per unit of quantity (e.g. mining m³, industry ISK).",
                null=True,
            ),
        ),
    ]
