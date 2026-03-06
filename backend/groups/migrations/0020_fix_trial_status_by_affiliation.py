# Placeholder migration. The actual fix is run via the management command:
#   python manage.py fix_trial_status_by_affiliation
# See groups/management/commands/fix_trial_status_by_affiliation.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0019_sync_community_groups_after_backfill"),
    ]

    operations = []
