# Fields already ship on CampaignStructure in 0012; kept as a no-op so
# environments that applied the earlier additive migration stay consistent.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0013_campaignstructure_fitting_reinforce_hour"),
    ]

    operations = []
