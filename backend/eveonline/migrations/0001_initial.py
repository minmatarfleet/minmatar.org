# Generated by Django 4.2.8 on 2023-12-11 02:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("esi", "0012_fix_token_type_choices"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvePrimaryToken",
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
                (
                    "token",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="esi.token",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="eve_primary_token",
                        to="esi.token",
                    ),
                ),
            ],
        ),
    ]
