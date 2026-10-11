from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0009_purchase_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="discord_thread_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
