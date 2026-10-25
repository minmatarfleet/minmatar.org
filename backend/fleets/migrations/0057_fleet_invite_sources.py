from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0056_private_fleets"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefleetinvitewave",
            name="onboarding",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="evefleetinvite",
            name="source_kind",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="evefleetinvite",
            name="source_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
