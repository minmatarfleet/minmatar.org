# Generated for tribe catalog report bindings

import re

from django.db import migrations, models
from django.utils.text import slugify


def _make_code(tribe_slug, group_name):
    group_part = slugify(group_name) or "group"
    group_part = re.sub(r"[^a-z0-9-]", "", group_part)
    return f"{tribe_slug}.{group_part}"


def backfill_tribegroup_codes(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    used = set()
    for tg in TribeGroup.objects.select_related("tribe").order_by("pk"):
        base = _make_code(tg.tribe.slug, tg.name)
        code = base
        n = 2
        while (
            code in used
            or TribeGroup.objects.filter(code=code).exclude(pk=tg.pk).exists()
        ):
            code = f"{base}-{n}"
            n += 1
        tg.code = code
        tg.save(update_fields=["code"])
        used.add(code)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0020_add_tribegroupactivity_point_weights"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribegroup",
            name="code",
            field=models.CharField(
                help_text="Stable catalog key for reports and bindings (e.g. industry.mining).",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_tribegroup_codes, noop_reverse),
        migrations.AlterField(
            model_name="tribegroup",
            name="code",
            field=models.CharField(
                help_text="Stable catalog key for reports and bindings (e.g. industry.mining).",
                max_length=64,
                unique=True,
            ),
        ),
    ]
