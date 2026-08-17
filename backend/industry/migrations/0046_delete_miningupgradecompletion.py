# Remove MiningUpgradeCompletion (sovereignty mining completions).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0045_lp_store_offer_economics_freight_breakdown"),
    ]

    operations = [
        migrations.DeleteModel(name="MiningUpgradeCompletion"),
    ]
