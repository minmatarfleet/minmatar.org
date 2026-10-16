# Seed the FW payout codes and relabel site rows stored while the table was empty.

from django.db import migrations


def seed_codes_and_relabel_sites(apps, schema_editor):
    """Name the payout codes, then fix completions still marked unknown.

    The service import waits until migrate runs. Loading it at module import
    would touch models before the app registry is ready.
    """
    from django.utils import timezone

    from campaigns.models import CampaignSiteCompletion
    from campaigns.services.sites import (
        build_complex_completions,
        rescore_completions,
        seed_event_codes,
    )

    seed_event_codes()
    rescore_completions()

    oldest = (
        CampaignSiteCompletion.objects.order_by("occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )
    if oldest is None:
        return
    hours = int((timezone.now() - oldest).total_seconds() // 3600) + 1
    build_complex_completions(since_hours=max(hours, 1))


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0022_campaign_parties"),
        ("eveonline", "0106_merge_fw_payout_corporation_profile"),
    ]

    operations = [
        migrations.RunPython(
            seed_codes_and_relabel_sites, migrations.RunPython.noop
        ),
    ]
