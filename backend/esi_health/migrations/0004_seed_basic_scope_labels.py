"""Name the seven read-only scopes Basic gained on 2026-11-24.

Without a row the "Update ESI" task says "newer Basic scopes", which tells a
pilot nothing. They were added together, so a token lacks all or none of
them, and one shared label reads as one phrase: "A newer login adds
corporation roles, standings and saved fittings". Suggest is the same as
having no row; a superuser can still switch one to Don't ask.
"""

from datetime import date

from django.db import migrations

ADDED_ON = date(2026, 11, 24)
LABEL = "corporation roles, standings and saved fittings"
SCOPES = (
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_titles.v1",
    "esi-characters.read_medals.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_freelance_jobs.v1",
    "esi-fittings.read_fittings.v1",
    "esi-universe.read_structures.v1",
)


def seed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    for scope in SCOPES:
        ScopeRollout.objects.get_or_create(
            scope=scope,
            defaults={
                "scope_group": "Basic",
                "label": LABEL,
                "added_on": ADDED_ON,
                "mode": "suggest",
            },
        )


def unseed(apps, schema_editor):
    ScopeRollout = apps.get_model("esi_health", "ScopeRollout")
    ScopeRollout.objects.filter(scope__in=SCOPES).delete()


class Migration(migrations.Migration):
    dependencies = [("esi_health", "0003_seed_director_corporation_scopes")]

    operations = [migrations.RunPython(seed, unseed)]
