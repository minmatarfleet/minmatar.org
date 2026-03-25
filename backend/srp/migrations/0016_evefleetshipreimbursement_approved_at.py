from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("srp", "0015_rename_combatlog_evefleetshipreimbursement_combat_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefleetshipreimbursement",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
