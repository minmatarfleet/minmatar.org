# Industry order: identifier, contract_to, self_assign_maximum, assignment economics & delivery.

from django.db import migrations, models


def backfill_order_identifiers(apps, schema_editor):
    IndustryOrder = apps.get_model("industry", "IndustryOrder")
    for order in IndustryOrder.objects.all():
        order.order_identifier = f"legacy-{order.pk}"
        order.save(update_fields=["order_identifier"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0018_remove_completion_system_id_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="industryorder",
            name="contract_to",
            field=models.CharField(
                blank=True,
                help_text="Contract recipient name (character or corporation), free text.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="industryorder",
            name="order_identifier",
            field=models.CharField(
                help_text="Short slug for contracts / cross-reference (e.g. big-iron-hands).",
                max_length=64,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_order_identifiers, noop),
        migrations.AlterField(
            model_name="industryorder",
            name="order_identifier",
            field=models.CharField(
                help_text="Short slug for contracts / cross-reference (e.g. big-iron-hands).",
                max_length=64,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorderitem",
            name="self_assign_maximum",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Per-character assignment cap for the first 48 hours after the order was "
                    "created; after that window, only total line quantity limits assignments."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorderitemassignment",
            name="delivered_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When this assignment was marked delivered.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorderitemassignment",
            name="target_estimated_margin",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Target estimated margin (ISK); set in admin.",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="industryorderitemassignment",
            name="target_unit_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Target unit price (ISK); set in admin.",
                max_digits=20,
                null=True,
            ),
        ),
    ]
