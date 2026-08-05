# Generated manually for buy-side below-set LP price flag.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0042_lp_store_offer_economics_involves_skin"),
    ]

    operations = [
        migrations.AddField(
            model_name="industrylpstoreoffereconomics",
            name="is_below_set_lp_price_buy",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
