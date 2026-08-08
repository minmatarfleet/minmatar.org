from django.db import migrations

GROUP_NAMES = ("People Team", "Technology Team", "Tribe - Chief")
PERM_CODENAME = "view_alliancehealth"


def grant_health_permission(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    AllianceHealthSnapshot = apps.get_model(
        "alliance", "AllianceHealthSnapshot"
    )

    content_type = ContentType.objects.get_for_model(AllianceHealthSnapshot)
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=PERM_CODENAME,
        defaults={"name": "Can view alliance health dashboard"},
    )
    for name in GROUP_NAMES:
        group = Group.objects.filter(name=name).first()
        if group is None:
            continue
        group.permissions.add(permission)


def revoke_health_permission(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    AllianceHealthSnapshot = apps.get_model(
        "alliance", "AllianceHealthSnapshot"
    )

    content_type = ContentType.objects.get_for_model(AllianceHealthSnapshot)
    permission = Permission.objects.filter(
        content_type=content_type, codename=PERM_CODENAME
    ).first()
    if permission is None:
        return
    for name in GROUP_NAMES:
        group = Group.objects.filter(name=name).first()
        if group is None:
            continue
        group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("alliance", "0001_alliance_health_snapshot"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(
            grant_health_permission, revoke_health_permission
        ),
    ]
