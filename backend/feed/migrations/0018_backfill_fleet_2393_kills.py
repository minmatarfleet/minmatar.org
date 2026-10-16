"""Populate the fleet_kills card for BearThatCares's fleet 2393.

That fleet (2026-10-15, Todifrauan complexes then a Crimson Harvest roam)
killed the Vargur and the Akoman that prompted this feature. Later fleets are
picked up by the feed rollup; this one may have ended outside its 48-hour
window by the time the migration runs.

It calls the live rollup code because the matching is app logic, not schema.
It does nothing where fleet 2393 is not BearThatCares's (dev, CI).
"""

from django.db import migrations

FLEET_ID = 2393
FC_USERNAME = "bearthatcares"


def backfill(apps, schema_editor):
    # Ask the historical model first. On a fresh database (tests, CI) this
    # finds nothing and the live models, whose columns may be newer than
    # this migration, are never queried.
    historical = apps.get_model("fleets", "EveFleetInstance")
    if not historical.objects.filter(
        eve_fleet_id=FLEET_ID,
        eve_fleet__created_by__username=FC_USERNAME,
    ).exists():
        return

    # Live models on purpose: the rollup writer needs them.
    # pylint: disable=import-outside-toplevel
    from feed.rollups.fleet_kills import build_fleet_kills_result
    from feed.rollups.writer import write_rollup_results
    from fleets.models import EveFleetInstance

    instances = EveFleetInstance.objects.filter(
        eve_fleet_id=FLEET_ID,
        eve_fleet__created_by__username=FC_USERNAME,
    )
    results = [
        result
        for result in (build_fleet_kills_result(i) for i in instances)
        if result is not None
    ]
    write_rollup_results(results)


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0017_fleet_kills_kind"),
        ("fleets", "0047_merge_campaign_hide_volunteers"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
