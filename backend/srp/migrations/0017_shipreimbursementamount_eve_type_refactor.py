from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("eveuniverse", "0001_initial"),
        ("srp", "0016_shipreimbursementamount_program_key_and_eve_type_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="shipreimbursementamount",
            name="kind",
        ),
        migrations.RemoveField(
            model_name="shipreimbursementamount",
            name="name",
        ),
        migrations.RemoveField(
            model_name="shipreimbursementamount",
            name="program_key",
        ),
        migrations.RemoveField(
            model_name="shipreimbursementamount",
            name="eve_type_id",
        ),
        migrations.AddField(
            model_name="shipreimbursementamount",
            name="eve_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="srp_reimbursement_values",
                to="eveuniverse.evetype",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="shipreimbursementamount",
            name="eve_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="srp_reimbursement_values",
                to="eveuniverse.evetype",
            ),
        ),
    ]
