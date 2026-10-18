# Nothing ever wrote these; the roster works them out live.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0029_recount_fleet_rejoins"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="campaignparticipantstat",
            name="characters_included",
        ),
        migrations.RemoveField(
            model_name="campaignparticipantstat",
            name="characters_lapsed",
        ),
        migrations.RemoveField(
            model_name="campaignparticipantstat",
            name="characters_tracked",
        ),
    ]
