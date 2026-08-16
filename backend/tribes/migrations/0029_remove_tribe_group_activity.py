# Remove tribe group activity ingest models.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0028_tribegroup_required_token_type"),
    ]

    operations = [
        migrations.DeleteModel(name="TribeGroupActivityRecord"),
        migrations.DeleteModel(name="TribeGroupActivity"),
    ]
