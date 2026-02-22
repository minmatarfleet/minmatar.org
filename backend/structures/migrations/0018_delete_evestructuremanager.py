# Structure notifications now use directors with esi-characters.read_notifications.v1
# in corporations that have structures; EveStructureManager is no longer used.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0017_evestructureping_event_time_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="EveStructureManager"),
    ]
