"""
Enforce a single TribeGroupMembership row per (tribe_group, user) pair.

Data migration: for any (tribe_group, user) combo that currently has more than
one row, keep the row with the highest-priority status (active > pending >
inactive) and, among ties, the most recently created. The losers are deleted
(their cascade-deleted history rows are acceptable to lose at this stage since
the duplicate rows are data anomalies from the old partial-constraint era).

Schema change: replace the conditional unique constraint (status='active' only)
with a full unique constraint.
"""

from django.db import migrations, models


def _status_priority(status: str) -> int:
    return {"active": 0, "pending": 1, "inactive": 2}.get(status, 99)


def deduplicate_memberships(apps, schema_editor):
    TribeGroupMembership = apps.get_model("tribes", "TribeGroupMembership")

    # Find (tribe_group, user) pairs that have more than one row.
    from django.db.models import Count

    duplicates = (
        TribeGroupMembership.objects.values("tribe_group_id", "user_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )

    for row in duplicates:
        memberships = list(
            TribeGroupMembership.objects.filter(
                tribe_group_id=row["tribe_group_id"],
                user_id=row["user_id"],
            ).order_by("created_at")
        )

        # Sort: prefer active, then pending, then inactive; within same status keep newest.
        memberships.sort(key=lambda m: (_status_priority(m.status), -m.pk))

        # Keep the first (highest priority / newest) and delete the rest.
        to_delete = [m.pk for m in memberships[1:]]
        TribeGroupMembership.objects.filter(pk__in=to_delete).delete()


def reverse_deduplicate(apps, schema_editor):
    pass  # Irreversible — deleted rows cannot be restored.


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0013_remove_tribe_activity"),
    ]

    operations = [
        # 1. Deduplicate before adding the constraint.
        migrations.RunPython(deduplicate_memberships, reverse_deduplicate),
        # 2. Drop the old partial unique constraint.
        migrations.RemoveConstraint(
            model_name="tribegroupmembership",
            name="tribes_tribegroupmembership_one_active_per_user_group",
        ),
        # 3. Add the full unique constraint.
        migrations.AddConstraint(
            model_name="tribegroupmembership",
            constraint=models.UniqueConstraint(
                fields=("tribe_group", "user"),
                name="tribes_tribegroupmembership_unique_per_user_group",
            ),
        ),
    ]
