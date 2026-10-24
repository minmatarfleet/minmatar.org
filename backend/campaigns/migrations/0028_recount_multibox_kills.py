# Recount the days where one pilot had several characters on the same kill.

from django.db import migrations


def recount_multibox_days(apps, schema_editor):
    """Rebuild every day holding a mail one pilot was on with alts.

    Those mails used to count once per character, so a multiboxer's eight
    alts scored eight kills. The stats task only rebuilds today and
    yesterday, which would leave the older campaign days counting them.
    """
    from django.db.models import Count

    from campaigns.helpers import campaign_day
    from campaigns.models import Campaign, CampaignKillmailParticipant
    from campaigns.services.stats import materialise_days, rebuild_stats

    doubled = (
        CampaignKillmailParticipant.objects.filter(
            enlisted=True, user__isnull=False
        )
        .values("killmail__campaign_id", "killmail_id", "user_id", "role")
        .annotate(characters=Count("id"))
        .filter(characters__gt=1)
        .values_list("killmail__campaign_id", "killmail__killmail_time")
    )
    days_by_campaign: dict[int, set] = {}
    for campaign_id, moment in doubled:
        days_by_campaign.setdefault(campaign_id, set()).add(
            campaign_day(moment)
        )

    for campaign in Campaign.objects.filter(id__in=days_by_campaign):
        materialise_days(campaign, days_by_campaign[campaign.id])
        rebuild_stats(campaign)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0027_corporation_projects"),
    ]

    operations = [
        migrations.RunPython(recount_multibox_days, migrations.RunPython.noop),
    ]
