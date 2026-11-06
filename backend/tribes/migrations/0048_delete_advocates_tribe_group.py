"""Delete the Advocates tribe group and its auth group.

Cascades remove the group's memberships (and their history), requirements,
invitations, events, ranks and help-request category. Posts, orders, fleets
and feature gates only lose their link to the group. The Discord role itself
is not touched; remove it in Discord by hand.
"""

from django.db import migrations

CODE = "pulse.advocates"


def delete_advocates(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    Group = apps.get_model("auth", "Group")

    for tribe_group in TribeGroup.objects.filter(code=CODE):
        auth_group_id = tribe_group.group_id
        tribe_group.delete()
        if auth_group_id:
            Group.objects.filter(pk=auth_group_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0047_tribe_group_fleets_events_enabled"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # Irreversible: the rows are gone. Reversing is a no-op so the
        # schema can still roll back past this point.
        migrations.RunPython(delete_advocates, migrations.RunPython.noop),
    ]
