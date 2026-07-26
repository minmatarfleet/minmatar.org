from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0032_inferred_sales"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evemarketinferredsale",
            name="reason",
            field=models.CharField(
                choices=[
                    ("partial_fill", "Partial fill"),
                    ("sellout", "Sellout"),
                    ("imported", "Imported"),
                ],
                max_length=32,
            ),
        ),
    ]
