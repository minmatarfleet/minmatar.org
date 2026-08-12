from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0043_remove_fittingbuyorder_title"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fittingbuyorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_fitting", "Pending fitting"),
                    ("purchased", "Purchased"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=16,
            ),
        ),
    ]
