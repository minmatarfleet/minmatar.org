from django.db import migrations, models

FISHERMEN_GROUP_CODE = "pulse.fishermen"


def hide_fishermen_roster(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroup.objects.filter(code=FISHERMEN_GROUP_CODE).update(
        roster_hidden=True
    )


def show_fishermen_roster(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroup.objects.filter(code=FISHERMEN_GROUP_CODE).update(
        roster_hidden=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0038_seed_fishermen_external_guild"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribegroup",
            name="roster_hidden",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When set, only active members and people who manage this "
                    "group see names and portraits. Everyone else sees a count "
                    "of blurred placeholders."
                ),
            ),
        ),
        migrations.RunPython(hide_fishermen_roster, show_fishermen_roster),
    ]
