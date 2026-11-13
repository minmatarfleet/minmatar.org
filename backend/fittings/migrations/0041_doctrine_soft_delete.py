from django.db import migrations, models


def copy_retired_to_deleted(apps, schema_editor):
    """Retired doctrines become soft-deleted and drop out of every list."""
    EveDoctrine = apps.get_model("fittings", "EveDoctrine")
    EveDoctrine.objects.filter(retired_at__isnull=False).update(
        deleted=models.F("retired_at")
    )


def copy_deleted_to_retired(apps, schema_editor):
    EveDoctrine = apps.get_model("fittings", "EveDoctrine")
    EveDoctrine.objects.filter(deleted__isnull=False).update(
        retired_at=models.F("deleted")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0040_doctrine_retired_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="evedoctrine",
            name="deleted",
            field=models.DateTimeField(
                db_index=True, editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name="evedoctrine",
            name="deleted_by_cascade",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(copy_retired_to_deleted, copy_deleted_to_retired),
        migrations.AlterField(
            model_name="evedoctrine",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AddConstraint(
            model_name="evedoctrine",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted__isnull", True)),
                fields=("name",),
                name="unique_evedoctrine_name_not_deleted",
            ),
        ),
        migrations.RemoveField(
            model_name="evedoctrine",
            name="retired_at",
        ),
    ]
