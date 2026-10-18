# Rebuild the days a pilot lost when they rejoined a campaign fleet.

from datetime import timedelta

from django.db import migrations


def recount_rejoined_days(apps, schema_editor):
    """Rebuild every campaign day between a member's first sighting and their
    latest ESI join_time, and the rest of each of those weeks.

    ESI moves join_time forward when a pilot drops and rejoins, and the
    attendance query used to start the pilot's window there, so a rebuild of
    an earlier day dropped them from it. The stats task only rebuilds today
    and yesterday, which would leave older days short. The rest of the week
    is rebuilt too, because a day's contribution-mix bonus reads the days
    before it.
    """
    from campaigns.helpers import campaign_day, week_start_for
    from campaigns.models import Campaign
    from campaigns.services.stats import materialise_days, rebuild_stats
    from fleets.models import EveFleetInstanceMember

    today = campaign_day()
    days_by_campaign: dict[int, set] = {}
    rows = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet__campaign__isnull=False,
        created_at__isnull=False,
    ).values_list(
        "eve_fleet_instance__eve_fleet__campaign_id",
        "created_at",
        "join_time",
    )
    for campaign_id, created_at, join_time in rows:
        first = campaign_day(created_at)
        rejoined = campaign_day(join_time)
        if first >= rejoined:
            continue
        days = days_by_campaign.setdefault(campaign_id, set())
        day = first
        last = min(week_start_for(rejoined) + timedelta(days=6), today)
        while day <= last:
            days.add(day)
            day += timedelta(days=1)

    for campaign in Campaign.objects.filter(id__in=days_by_campaign):
        materialise_days(campaign, days_by_campaign[campaign.id])
        rebuild_stats(campaign)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0028_recount_multibox_kills"),
        ("fleets", "0046_evefleet_campaign_alter_evefleet_type_and_more"),
    ]

    operations = [
        migrations.RunPython(recount_rejoined_days, migrations.RunPython.noop),
    ]
