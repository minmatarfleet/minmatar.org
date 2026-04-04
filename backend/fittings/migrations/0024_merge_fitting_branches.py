# Merges parallel branches: 0020_alter_evefitting_name_remove_unique vs 0020_eve_fitting_history → … → 0023.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0020_alter_evefitting_name_remove_unique"),
        ("fittings", "0023_backfill_evefitting_tags_from_name"),
    ]

    operations = []
