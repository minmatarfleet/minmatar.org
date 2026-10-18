"""Link tribe groups to their channel in the Discord Tribes category.

Discord is the source of truth. Only groups with no channel yet are set.
Groups are matched by the slug after the tribe prefix: supply.* (or the
older industry.*) and pulse.*. #production is left alone (it is unclear
whether it belongs to subcapital or capital production) and Capitals
groups keep the #capitals tribe fallback.
"""

from django.db import migrations

GROUP_CHANNELS = {
    "mining": 1450351308027592715,
    "freighters": 1465125012901203983,
    "market": 1490366732458528981,
    "planetary-interaction": 1480262027485380659,
    "technology": 1174095095537078312,
    "readiness": 1391028680934822018,
    "thinkspeak": 1172908092573360149,
    "fleet-commanders": 1475181633232437408,
}
PREFIXES = ("supply", "industry", "pulse")


def link_channels(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    for slug, channel_id in GROUP_CHANNELS.items():
        codes = [f"{prefix}.{slug}" for prefix in PREFIXES]
        TribeGroup.objects.filter(
            code__in=codes, discord_channel_id__isnull=True
        ).update(discord_channel_id=channel_id)


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0043_tribe_publishing"),
    ]

    operations = [
        migrations.RunPython(link_channels, migrations.RunPython.noop),
    ]
