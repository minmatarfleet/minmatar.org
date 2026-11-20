"""The two scopes added to a group after most tokens were granted.

- Basic gained structure search with live Faction Warfare campaigns (#2787,
  2026-10-14). 664 of 824 working alliance tokens predate it and only
  structure search uses it, so nobody is asked.
- Director gained corporation projects (#2840, 2026-10-17). Six of ten
  corporations' director tokens predate it and their Projects tab is empty,
  so CEOs and directors get a task.
"""

from datetime import date

from django.db import migrations

ROLLOUTS = (
    (
        "esi-search.search_structures.v1",
        "Basic",
        "structure search",
        date(2026, 10, 14),
        "none",
    ),
    (
        "esi-corporations.read_projects.v1",
        "Director",
        "corporation projects",
        date(2026, 10, 17),
        "require",
    ),
)


def seed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    for scope, group, label, added_on, mode in ROLLOUTS:
        ScopeRollout.objects.get_or_create(
            scope=scope,
            defaults={
                "scope_group": group,
                "label": label,
                "added_on": added_on,
                "mode": mode,
            },
        )


def unseed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    ScopeRollout.objects.filter(
        scope__in=[row[0] for row in ROLLOUTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("esi_health", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
