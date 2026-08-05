# Generated manually for 7d average price / conversion / below-set flag.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0043_lp_store_offer_economics_below_set_buy"),
    ]

    operations = [
        migrations.AddField(
            model_name="industrylpstoreoffereconomics",
            name="jita_avg_7d",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="industrylpstoreoffereconomics",
            name="conversion_isk_per_lp_avg_7d",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="industrylpstoreoffereconomics",
            name="is_below_set_lp_price_avg_7d",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
