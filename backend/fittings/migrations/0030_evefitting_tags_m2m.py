# Replace EveFitting.tags JSONField with EveFittingTag M2M.

import json

from django.db import migrations, models

REMOVED_TAGS = frozenset({"lowsec", "solo", "budget"})

FITTING_TAG_SEED = (
    ("highsec", "Highsec"),
    ("nullsec", "Nullsec"),
    ("faction_warfare", "Faction warfare"),
    ("nanogang", "Nanogang"),
    ("fleet_composition", "Fleet Composition"),
    ("new_player_friendly", "New Player Friendly"),
    ("capitals", "Capitals"),
    ("command_bursts", "Command Bursts"),
    ("industry", "Industry"),
    ("escape_frigate", "Escape Frigate"),
)


def seed_tags(apps, schema_editor):
    Tag = apps.get_model("fittings", "EveFittingTag")
    for slug, label in FITTING_TAG_SEED:
        Tag.objects.get_or_create(slug=slug, defaults={"label": label})


def backfill_tags(apps, schema_editor):
    Fitting = apps.get_model("fittings", "EveFitting")
    Tag = apps.get_model("fittings", "EveFittingTag")
    allowed = {slug for slug, _ in FITTING_TAG_SEED}
    by_slug = {t.slug: t for t in Tag.objects.all()}

    for fitting in Fitting.objects.iterator(chunk_size=500):
        raw = fitting.tags_legacy
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = []
        if not isinstance(raw, list):
            continue
        tags = [
            by_slug[s]
            for s in raw
            if isinstance(s, str) and s in allowed and s not in REMOVED_TAGS
        ]
        if tags:
            fitting.tags.set(tags)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0029_eve_fitting_module_substitution"),
    ]

    operations = [
        migrations.CreateModel(
            name="EveFittingTag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("label", models.CharField(max_length=64)),
            ],
            options={"ordering": ["slug"]},
        ),
        migrations.RunPython(seed_tags, noop),
        migrations.RenameField(
            model_name="evefitting",
            old_name="tags",
            new_name="tags_legacy",
        ),
        migrations.AddField(
            model_name="evefitting",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                related_name="fittings",
                to="fittings.evefittingtag",
            ),
        ),
        migrations.RunPython(backfill_tags, noop),
        migrations.RemoveField(
            model_name="evefitting",
            name="tags_legacy",
        ),
    ]
