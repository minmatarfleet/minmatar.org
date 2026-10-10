from django.db import migrations, models

PERM_CODENAME = "manage_any_fleet"
STRATEGIC_FC_GROUP = "Strategic FC"


def grant_manage_any_fleet(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    EveFleet = apps.get_model("fleets", "EveFleet")

    content_type = ContentType.objects.get_for_model(EveFleet)
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=PERM_CODENAME,
        defaults={"name": "Can manage any fleet"},
    )
    group, _ = Group.objects.get_or_create(name=STRATEGIC_FC_GROUP)
    group.permissions.add(permission)


def revoke_manage_any_fleet(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    EveFleet = apps.get_model("fleets", "EveFleet")

    content_type = ContentType.objects.get_for_model(EveFleet)
    permission = Permission.objects.filter(
        content_type=content_type, codename=PERM_CODENAME
    ).first()
    if permission is None:
        return
    group = Group.objects.filter(name=STRATEGIC_FC_GROUP).first()
    if group is not None:
        group.permissions.remove(permission)


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0045_evefleet_roam_report_url"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefleet",
            name="hide_volunteers",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterModelOptions(
            name="evefleet",
            options={
                "permissions": [
                    ("manage_any_fleet", "Can manage any fleet"),
                ]
            },
        ),
        migrations.RunPython(grant_manage_any_fleet, revoke_manage_any_fleet),
    ]
