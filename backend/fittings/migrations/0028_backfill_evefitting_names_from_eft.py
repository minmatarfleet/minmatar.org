# Align EveFitting / EveFittingRefit.name with the EFT header name.

from django.db import migrations


def _fitting_name_from_eft(eft_format: str) -> str:
    if not (eft_format and str(eft_format).strip()):
        return ""
    parts = str(eft_format).split("\n")[0].split(",", 1)
    if len(parts) < 2:
        return ""
    fitting_name = parts[1].strip()
    if fitting_name.endswith("]"):
        fitting_name = fitting_name[:-1].strip()
    return fitting_name


def backfill_names_from_eft(apps, schema_editor):
    EveFitting = apps.get_model("fittings", "EveFitting")
    EveFittingRefit = apps.get_model("fittings", "EveFittingRefit")
    db_alias = schema_editor.connection.alias
    fitting_manager = EveFitting._base_manager.using(db_alias)
    refit_manager = EveFittingRefit._base_manager.using(db_alias)

    for fitting in fitting_manager.iterator(chunk_size=500):
        derived = _fitting_name_from_eft(fitting.eft_format)
        if not derived or derived == fitting.name:
            continue
        if fitting.deleted is None:
            collision = (
                fitting_manager.filter(name=derived, deleted__isnull=True)
                .exclude(pk=fitting.pk)
                .exists()
            )
            if collision:
                continue
        fitting_manager.filter(pk=fitting.pk).update(name=derived)

    for refit in refit_manager.iterator(chunk_size=500):
        derived = _fitting_name_from_eft(refit.eft_format)
        if not derived or derived == refit.name:
            continue
        collision = (
            refit_manager.filter(
                base_fitting_id=refit.base_fitting_id, name=derived
            )
            .exclude(pk=refit.pk)
            .exists()
        )
        if collision:
            continue
        refit_manager.filter(pk=refit.pk).update(name=derived)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0027_migrate_legacy_pod_text"),
    ]

    operations = [
        migrations.RunPython(backfill_names_from_eft, noop_reverse),
    ]
