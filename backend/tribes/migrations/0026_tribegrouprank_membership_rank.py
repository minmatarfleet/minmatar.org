# Tribe group ranks and nullable membership rank FK.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0025_remove_help_tickets"),
    ]

    operations = [
        migrations.CreateModel(
            name="TribeGroupRank",
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
                ("name", models.CharField(max_length=128)),
                (
                    "code",
                    models.CharField(
                        help_text="Stable key within the tribe group (e.g. strategic).",
                        max_length=64,
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Lower values sort first in UI lists.",
                    ),
                ),
                (
                    "tribe_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ranks",
                        to="tribes.tribegroup",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="tribegrouprank",
            constraint=models.UniqueConstraint(
                fields=("tribe_group", "code"),
                name="tribes_tribegrouprank_unique_code_per_group",
            ),
        ),
        migrations.AddField(
            model_name="tribegroupmembership",
            name="rank",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="memberships",
                to="tribes.tribegrouprank",
            ),
        ),
    ]
