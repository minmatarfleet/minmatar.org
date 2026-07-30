# Seed ORDERS onboarding program and widen program_type choices.

import uuid

from django.db import migrations, models

ORDERS_INITIAL_VERSION = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def seed_orders_program(apps, schema_editor):
    OnboardingProgram = apps.get_model("onboarding", "OnboardingProgram")
    OnboardingProgram.objects.get_or_create(
        program_type="orders",
        defaults={"version": ORDERS_INITIAL_VERSION},
    )


def unseed_orders_program(apps, schema_editor):
    OnboardingProgram = apps.get_model("onboarding", "OnboardingProgram")
    OnboardingProgram.objects.filter(program_type="orders").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0002_rename_slug_onboardingprogram_program_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="onboardingprogram",
            name="program_type",
            field=models.CharField(
                choices=[("srp", "SRP"), ("orders", "Orders")],
                max_length=32,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.RunPython(seed_orders_program, unseed_orders_program),
    ]
