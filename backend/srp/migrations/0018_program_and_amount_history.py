from django.db import migrations, models
import django.db.models.deletion


def seed_initial_program_amounts(apps, schema_editor):
    Program = apps.get_model("srp", "ShipReimbursementProgram")
    ProgramAmount = apps.get_model("srp", "ShipReimbursementProgramAmount")
    for program in Program.objects.all().iterator():
        ProgramAmount.objects.create(
            program_id=program.id,
            srp_value=program.srp_value,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("srp", "0017_shipreimbursementamount_eve_type_refactor"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ShipReimbursementAmount",
            new_name="ShipReimbursementProgram",
        ),
        migrations.AlterField(
            model_name="shipreimbursementprogram",
            name="eve_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="srp_reimbursement_programs",
                to="eveuniverse.evetype",
            ),
        ),
        migrations.CreateModel(
            name="ShipReimbursementProgramAmount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("srp_value", models.BigIntegerField()),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                (
                    "program",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="amounts",
                        to="srp.shipreimbursementprogram",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="evefleetshipreimbursement",
            name="reimbursement_program_amount",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="srp.shipreimbursementprogramamount",
            ),
        ),
        migrations.RunPython(
            seed_initial_program_amounts, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="shipreimbursementprogram",
            name="srp_value",
        ),
    ]
