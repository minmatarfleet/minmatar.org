from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0002_order_date_needed_by_character"),
    ]

    operations = [
        migrations.AddField(
            model_name="industryorder",
            name="fulfilled_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When this order was marked as fulfilled.",
                null=True,
            ),
        ),
    ]
