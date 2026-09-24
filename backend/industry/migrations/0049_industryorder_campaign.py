# Generated manually for campaign FK on IndustryOrder.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0012_campaign_kinds_and_structures"),
        ("industry", "0048_industryloyaltypoint_allow_buy_sell"),
    ]

    operations = [
        migrations.AddField(
            model_name="industryorder",
            name="campaign",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional live campaign this supply order supports.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="industry_orders",
                to="campaigns.campaign",
            ),
        ),
    ]
