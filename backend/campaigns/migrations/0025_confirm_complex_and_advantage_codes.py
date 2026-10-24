# Confirm the October complex and advantage codes, then recount the days they touch.

from django.db import migrations

# (event code, the kind it must already be labelled as). A row somebody
# relabelled by hand is left alone.
CONFIRMED_CODES = (
    (359, "complex"),
    (373, "complex"),
    (516, "advantage_site"),
)


def confirm_codes_and_recount(apps, schema_editor):
    """Confirm the codes, rescore their sites and rebuild the affected days.

    Seeding never flips ``confirmed`` on an existing row, so the codes are
    confirmed here once. The stats task only rebuilds today and yesterday,
    which would leave older campaign days counting none of these sites.
    """
    from django.utils import timezone

    from campaigns.helpers import campaign_day
    from campaigns.models import Campaign, CampaignSiteCompletion
    from campaigns.services.sites import (
        rescore_completions,
        seed_event_codes,
    )
    from campaigns.services.stats import materialise_days, rebuild_stats
    from eveonline.models import FwPayoutEventCode

    seed_event_codes()
    for code, kind in CONFIRMED_CODES:
        FwPayoutEventCode.objects.filter(
            event_code=code, site_kind=kind, confirmed=False
        ).update(
            confirmed=True,
            confirmed_by="Live payouts, Aldodan YC128",
            confirmed_at=timezone.now(),
        )
        rescore_completions(event_code=code)

    codes = [code for code, _ in CONFIRMED_CODES]
    for campaign in Campaign.objects.filter(
        site_completions__event_code__in=codes
    ).distinct():
        moments = CampaignSiteCompletion.objects.filter(
            campaign=campaign, event_code__in=codes
        ).values_list("occurred_at", flat=True)
        materialise_days(campaign, {campaign_day(m) for m in moments})
        rebuild_stats(campaign)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0024_seed_fw_event_codes"),
    ]

    operations = [
        migrations.RunPython(
            confirm_codes_and_recount, migrations.RunPython.noop
        ),
    ]
