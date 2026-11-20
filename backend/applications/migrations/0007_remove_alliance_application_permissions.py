# The Alliance auth group is every member. It was holding the recruiter
# permissions, so every member saw other corporations' applications.

from django.db import migrations

ALLIANCE_AUTH_GROUP = "Alliance"
APPLICATION_PERMISSION_CODENAMES = (
    "add_evecorporationapplication",
    "change_evecorporationapplication",
    "delete_evecorporationapplication",
    "view_evecorporationapplication",
)


def remove_alliance_application_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group = Group.objects.filter(name=ALLIANCE_AUTH_GROUP).first()
    if group is None:
        return
    permissions = Permission.objects.filter(
        content_type__app_label="applications",
        codename__in=APPLICATION_PERMISSION_CODENAMES,
    )
    group.permissions.remove(*list(permissions))


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0006_corporation_requirement"),
    ]

    operations = [
        migrations.RunPython(
            remove_alliance_application_permissions,
            migrations.RunPython.noop,
        ),
    ]
