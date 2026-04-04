# Backfill EveFitting.tags from bracket prefixes in fitting names.

from django.db import migrations


def _infer_tags_from_name(name: str) -> set[str]:
    """
    Match bracket prefixes in stored fitting names (including numbered variants
    like [NVY-30], [ADV-5] used in production).
    """
    if not name:
        return set()
    inferred: set[str] = set()
    if "[L3ARN" in name:
        inferred.add("new_player_friendly")
    if "[NVY" in name:
        inferred.update(["faction_warfare", "solo"])
    if "[ADV" in name:
        inferred.add("nanogang")
    return inferred


def backfill_fitting_tags(apps, schema_editor):
    EveFitting = apps.get_model("fittings", "EveFitting")
    db_alias = schema_editor.connection.alias
    manager = EveFitting._base_manager.using(db_alias)

    for fitting in manager.iterator(chunk_size=500):
        inferred = _infer_tags_from_name(fitting.name)
        if not inferred:
            continue
        current = set(fitting.tags or [])
        if inferred <= current:
            continue
        merged = sorted(current | inferred)
        manager.filter(pk=fitting.pk).update(tags=merged)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0022_fitting_tags"),
    ]

    operations = [
        migrations.RunPython(backfill_fitting_tags, noop_reverse),
    ]
