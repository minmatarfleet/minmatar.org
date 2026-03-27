from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("srp", "0015_rename_combatlog_evefleetshipreimbursement_combat_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipreimbursementamount",
            name="eve_type_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shipreimbursementamount",
            name="program_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
