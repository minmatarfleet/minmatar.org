# Generated for industry MiningUpgradeCompletion

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("industry", "0014_strategy_imported_harvested_produced"),
    ]

    operations = [
        migrations.CreateModel(
            name="MiningUpgradeCompletion",
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
                ("system_id", models.BigIntegerField(db_index=True)),
                ("system_name", models.CharField(blank=True, max_length=255)),
                ("completed_at", models.DateTimeField()),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="mining_upgrade_completions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Mining upgrade completion",
                "verbose_name_plural": "Mining upgrade completions",
                "ordering": ["-completed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="miningupgradecompletion",
            index=models.Index(
                fields=["system_id", "-completed_at"],
                name="industry_mi_system__a2c8b4_idx",
            ),
        ),
    ]
