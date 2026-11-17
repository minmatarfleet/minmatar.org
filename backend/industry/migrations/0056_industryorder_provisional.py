# Provisional claiming period on industry orders.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveuniverse", "0012_alter_evebloodline_eve_ship_type"),
        ("industry", "0055_invention_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="industryorder",
            name="starts_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "When a provisional order stops taking claims and selected "
                    "builders are told to start. Empty means the order is open "
                    "immediately."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorder",
            name="started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the provisional claiming period was closed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorder",
            name="selection_notified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When selected builders were told to start immediately.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="industryorder",
            index=models.Index(
                fields=["starts_at"],
                name="industry_order_starts_at_idx",
            ),
        ),
        migrations.CreateModel(
            name="IndustryOrderUnfulfilledItem",
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
                ("quantity", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "eve_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="eveuniverse.evetype",
                    ),
                ),
                (
                    "imported_into",
                    models.ForeignKey(
                        blank=True,
                        help_text="Later order this remainder was imported into.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="imported_unfulfilled_items",
                        to="industry.industryorder",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unfulfilled_items",
                        to="industry.industryorder",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
