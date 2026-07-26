# Generated manually for IndustryContractAssociation

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0028_seed_militia_loyalty_points"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndustryContractAssociation",
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
                    "contract_id",
                    models.BigIntegerField(
                        db_index=True,
                        help_text="ESI contract_id (no FK; survives character-contract re-sync).",
                    ),
                ),
                (
                    "score",
                    models.FloatField(
                        help_text="Loose match confidence from 0 to 1.",
                    ),
                ),
                (
                    "signals",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Which signals contributed to the score.",
                    ),
                ),
                (
                    "contract_status",
                    models.CharField(
                        blank=True,
                        help_text="ESI contract status snapshot at match time.",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        help_text="Set when issuer/items pin the contract to one assignment.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_associations",
                        to="industry.industryorderitemassignment",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_associations",
                        to="industry.industryorder",
                    ),
                ),
            ],
            options={
                "ordering": ["-score", "-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="industrycontractassociation",
            index=models.Index(
                fields=["order", "contract_id"],
                name="industry_in_order_i_7c2a1b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="industrycontractassociation",
            index=models.Index(
                fields=["contract_id", "score"],
                name="industry_in_contrac_9f4e2d_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="industrycontractassociation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("assignment__isnull", False)),
                fields=("assignment", "contract_id"),
                name="uniq_industry_contract_assoc_assignment_contract",
            ),
        ),
        migrations.AddConstraint(
            model_name="industrycontractassociation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("assignment__isnull", True)),
                fields=("order", "contract_id"),
                name="uniq_industry_contract_assoc_order_contract",
            ),
        ),
    ]
