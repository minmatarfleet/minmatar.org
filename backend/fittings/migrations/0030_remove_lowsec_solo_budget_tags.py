# Remove retired fitting tags (lowsec, solo, budget) from stored JSON.

from django.db import migrations

REMOVED_TAGS = frozenset({"lowsec", "solo", "budget"})


def _strip_removed_tags(tags):
    if not isinstance(tags, list):
        return [], False
    original = [t for t in tags if isinstance(t, str)]
    if not any(t in REMOVED_TAGS for t in original):
        return tags, False
    cleaned = sorted({t for t in original if t not in REMOVED_TAGS})
    return cleaned, True


def remove_retired_fitting_tags(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    EveFitting = apps.get_model("fittings", "EveFitting")
    for fitting in EveFitting._base_manager.using(db_alias).iterator(
        chunk_size=500
    ):
        cleaned, changed = _strip_removed_tags(fitting.tags)
        if changed:
            EveFitting._base_manager.using(db_alias).filter(
                pk=fitting.pk
            ).update(tags=cleaned)

    EveFittingHistory = apps.get_model("fittings", "EveFittingHistory")
    for row in EveFittingHistory.objects.using(db_alias).iterator(
        chunk_size=500
    ):
        cleaned, changed = _strip_removed_tags(row.tags)
        if changed:
            EveFittingHistory.objects.using(db_alias).filter(pk=row.pk).update(
                tags=cleaned
            )

    EveLocation = apps.get_model("eveonline", "EveLocation")
    for location in EveLocation.objects.using(db_alias).iterator(
        chunk_size=500
    ):
        cleaned, changed = _strip_removed_tags(location.market_categories)
        if changed:
            EveLocation.objects.using(db_alias).filter(pk=location.pk).update(
                market_categories=cleaned
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0029_eve_fitting_module_substitution"),
        ("eveonline", "0096_evecharacter_active_implants"),
    ]

    operations = [
        migrations.RunPython(remove_retired_fitting_tags, noop_reverse),
    ]
