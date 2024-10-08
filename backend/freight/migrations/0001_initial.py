# Generated by Django 5.1 on 2024-08-25 03:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EveFreightLocation",
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
                ("location_id", models.BigIntegerField(unique=True)),
                ("name", models.CharField(max_length=255)),
                ("short_name", models.CharField(max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name="EveFreightRoute",
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
                ("bidirectional", models.BooleanField(default=True)),
                (
                    "destination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="destination",
                        to="freight.evefreightlocation",
                    ),
                ),
                (
                    "orgin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orgin",
                        to="freight.evefreightlocation",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EveFreightRouteOption",
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
                ("base_cost", models.BigIntegerField()),
                ("collateral_modifier", models.FloatField()),
                ("maximum_m3", models.BigIntegerField()),
                (
                    "route",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="freight.evefreightroute",
                    ),
                ),
            ],
        ),
    ]
