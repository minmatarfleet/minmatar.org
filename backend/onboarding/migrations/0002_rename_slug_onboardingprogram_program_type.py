# Rename slug to program_type (hardcoded onboarding program identifiers).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="onboardingprogram",
            old_name="slug",
            new_name="program_type",
        ),
        migrations.AlterField(
            model_name="onboardingprogram",
            name="program_type",
            field=models.CharField(
                choices=[("srp", "SRP")],
                max_length=32,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
