from django.db import migrations, models


def forwards_purchased_to_completed(apps, schema_editor):
    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    FittingBuyOrder.objects.filter(status="purchased").update(
        status="completed"
    )


def backwards_completed_to_purchased(apps, schema_editor):
    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    FittingBuyOrder.objects.filter(status="completed").update(
        status="purchased"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0048_fittingbuyorder_stock_paste_nullable"),
    ]

    operations = [
        migrations.RunPython(
            forwards_purchased_to_completed,
            backwards_completed_to_purchased,
        ),
        migrations.AlterField(
            model_name="fittingbuyorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_fitting", "Pending fitting"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=16,
            ),
        ),
    ]
