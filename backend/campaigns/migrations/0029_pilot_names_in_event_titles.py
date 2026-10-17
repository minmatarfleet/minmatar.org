"""Name pilots by their main in award and gang event titles.

Award and gang-formed titles used to embed ``User.username``, which is the
member's Discord handle, and the timeline of a public campaign is readable
anonymously. Rewrite those titles to the pilot's main character name. The
original title is kept in ``payload["legacy_title"]`` (payload is never
returned by the API), so the migration reverses exactly.
"""

from django.db import migrations

UNKNOWN_PILOT = "Unknown pilot"
KINDS = ("award", "gang_formed")
TITLE_MAX = 256


def _main_names(apps, user_ids) -> dict[int, str]:
    EvePlayer = apps.get_model("eveonline", "EvePlayer")
    return {
        player.user_id: player.primary_character.character_name
        for player in EvePlayer.objects.filter(
            user_id__in=list(user_ids), primary_character__isnull=False
        ).select_related("primary_character")
    }


def _renamed(event, username: str, name: str) -> str | None:
    title = event.title or ""
    if event.kind == "award":
        suffix = f": {username}"
        if title.endswith(suffix):
            return f"{title[: -len(suffix)]}: {name}"
    else:
        prefix = f"{username} is forming "
        if title.startswith(prefix):
            return f"{name} is forming {title[len(prefix):]}"
    return None


def forwards(apps, schema_editor):
    CampaignEvent = apps.get_model("campaigns", "CampaignEvent")
    events = list(
        CampaignEvent.objects.filter(
            kind__in=KINDS, user__isnull=False
        ).select_related("user")
    )
    names = _main_names(apps, {event.user_id for event in events})
    for event in events:
        payload = dict(event.payload or {})
        if "legacy_title" in payload or not event.user.username:
            continue
        title = _renamed(
            event,
            event.user.username,
            names.get(event.user_id, UNKNOWN_PILOT),
        )
        if title is None or title == event.title:
            continue
        payload["legacy_title"] = event.title
        event.title = title[:TITLE_MAX]
        event.payload = payload
        event.save(update_fields=["title", "payload"])


def backwards(apps, schema_editor):
    CampaignEvent = apps.get_model("campaigns", "CampaignEvent")
    for event in CampaignEvent.objects.filter(kind__in=KINDS):
        payload = dict(event.payload or {})
        if "legacy_title" not in payload:
            continue
        event.title = payload.pop("legacy_title")
        event.payload = payload
        event.save(update_fields=["title", "payload"])


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0028_recount_multibox_kills"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
