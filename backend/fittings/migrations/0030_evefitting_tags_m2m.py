# Replace EveFitting.tags JSONField with EveFittingTag M2M.

import json

from django.db import migrations, models

REMOVED_TAGS = frozenset({"lowsec", "solo", "budget"})

# Keep in sync with fittings.models.FittingTag choices at migration time.
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


def seed_fitting_tags(apps, schema_editor):
    EveFittingTag = apps.get_model("fittings", "EveFittingTag")
    for slug, label in FITTING_TAG_SEED:
        EveFittingTag.objects.update_or_create(
            slug=slug, defaults={"label": label}
        )


def backfill_fitting_tags(apps, schema_editor):
    EveFitting = apps.get_model("fittings", "EveFitting")
    EveFittingTag = apps.get_model("fittings", "EveFittingTag")
    allowed = {slug for slug, _ in FITTING_TAG_SEED}
    tags_by_slug = {t.slug: t for t in EveFittingTag.objects.all()}

    for fitting in EveFitting.objects.all().iterator(chunk_size=200):
        raw = fitting.tags_legacy
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = []
        if not isinstance(raw, list):
            raw = []
        slugs = sorted(
            {
                t
                for t in raw
                if isinstance(t, str)
                and t in allowed
                and t not in REMOVED_TAGS
            }
        )
        if not slugs:
            continue
        fitting.tags.set([tags_by_slug[s] for s in slugs if s in tags_by_slug])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

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
            options={
                "ordering": ["slug"],
            },
        ),
        migrations.RunPython(seed_fitting_tags, noop_reverse),
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
        migrations.RunPython(backfill_fitting_tags, noop_reverse),
        migrations.RemoveField(
            model_name="evefitting",
            name="tags_legacy",
        ),
    ]
