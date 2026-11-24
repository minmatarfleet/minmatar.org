"""Director gained every other corporation scope ESI has (2026-11-24).

No feature reads them yet, so no director token is counted as missing them
(Don't ask): corporations keep the director token state they had, and new
director logins carry them. A superuser can switch one to Require on
Manage › ESI health once a feature uses it.

Basic gained seven read-only scopes at the same time with no rows here: no
row means the "Update ESI" task asks for them, which is the point (one
re-login covers them all).
"""

from datetime import date

from django.db import migrations

ADDED_ON = date(2026, 11, 24)
ROLLOUTS = (
    ("esi-contracts.read_corporation_contracts.v1", "corporation contracts"),
    ("esi-corporations.read_freelance_jobs.v1", "corporation freelance jobs"),
    ("esi-industry.read_corporation_jobs.v1", "corporation industry jobs"),
    ("esi-industry.read_corporation_mining.v1", "corporation mining"),
    ("esi-markets.read_corporation_orders.v1", "corporation market orders"),
    ("esi-structures.read_corporation.v1", "corporation structures"),
)


def seed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    for scope, label in ROLLOUTS:
        ScopeRollout.objects.get_or_create(
            scope=scope,
            defaults={
                "scope_group": "Director",
                "label": label,
                "added_on": ADDED_ON,
                "mode": "none",
            },
        )


def unseed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    ScopeRollout.objects.filter(
        scope__in=[scope for scope, _ in ROLLOUTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("esi_health", "0002_seed_scope_rollouts")]

    operations = [migrations.RunPython(seed, unseed)]
