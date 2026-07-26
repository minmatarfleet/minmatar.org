from django.db import models


class IndustryContractAssociation(models.Model):
    """
    Soft-scored link between an ESI private contract and an industry order
    (optionally a specific assignment). Does not drive delivery behavior.
    """

    order = models.ForeignKey(
        "industry.IndustryOrder",
        on_delete=models.CASCADE,
        related_name="contract_associations",
    )
    assignment = models.ForeignKey(
        "industry.IndustryOrderItemAssignment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contract_associations",
        help_text="Set when issuer/items pin the contract to one assignment.",
    )
    contract_id = models.BigIntegerField(
        db_index=True,
        help_text="ESI contract_id (no FK; survives character-contract re-sync).",
    )
    score = models.FloatField(
        help_text="Loose match confidence from 0 to 1.",
    )
    signals = models.JSONField(
        default=dict,
        blank=True,
        help_text="Which signals contributed to the score.",
    )
    contract_status = models.CharField(
        max_length=32,
        blank=True,
        help_text="ESI contract status snapshot at match time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "contract_id"],
                condition=models.Q(assignment__isnull=False),
                name="uniq_industry_contract_assoc_assignment_contract",
            ),
            models.UniqueConstraint(
                fields=["order", "contract_id"],
                condition=models.Q(assignment__isnull=True),
                name="uniq_industry_contract_assoc_order_contract",
            ),
        ]
        indexes = [
            models.Index(fields=["order", "contract_id"]),
            models.Index(fields=["contract_id", "score"]),
        ]

    def __str__(self):
        target = (
            f"assignment {self.assignment_id}"
            if self.assignment_id
            else f"order {self.order_id}"
        )
        return (
            f"Contract {self.contract_id} → {target} "
            f"(score={self.score:.2f})"
        )
