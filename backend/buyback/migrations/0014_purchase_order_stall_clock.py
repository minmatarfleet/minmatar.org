from django.db import migrations, models
from django.db.models import F
from django.utils import timezone


def backfill_settlement_changed_at(apps, schema_editor):
    """Existing sales have been on this step since they were placed."""
    order_model = apps.get_model("buyback", "BuybackPurchaseOrder")
    order_model.objects.update(settlement_changed_at=F("created_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0013_purchase_order_settlement_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="cancel_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="settlement_changed_at",
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text=(
                    "When this settlement step started; drives reminders."
                ),
            ),
        ),
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="stalled_reminder_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Last stalled-sale reminder; cleared when the step "
                    "changes."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_settlement_changed_at, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="buybackpurchaseorder",
            name="settlement_step",
            field=models.CharField(
                choices=[
                    ("contract_up", "Contract up"),
                    ("awaiting_accept", "Awaiting accept"),
                    ("manual_close", "Close"),
                ],
                default="contract_up",
                max_length=32,
            ),
        ),
    ]
