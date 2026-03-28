# Generated manually for industry Discord public codes.

import secrets
import string

from django.db import migrations, models

_ALPHABET = string.ascii_letters + string.digits
_LEN = 3
_MAX_TRIES = 512


def _rand_code():
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LEN))


def _backfill_public_short_codes(apps, schema_editor):
    IndustryOrder = apps.get_model("industry", "IndustryOrder")
    active_codes = set(
        IndustryOrder.objects.filter(fulfilled_at__isnull=True)
        .exclude(public_short_code="")
        .values_list("public_short_code", flat=True)
    )
    for order in IndustryOrder.objects.all().order_by("pk"):
        if order.public_short_code:
            continue
        for _ in range(_MAX_TRIES):
            candidate = _rand_code()
            if order.fulfilled_at is None:
                if candidate in active_codes:
                    continue
                clash = IndustryOrder.objects.filter(
                    fulfilled_at__isnull=True,
                    public_short_code=candidate,
                ).exclude(pk=order.pk)
                if clash.exists():
                    continue
                active_codes.add(candidate)
            order.public_short_code = candidate
            order.save(update_fields=["public_short_code"])
            break
        else:
            raise RuntimeError(
                f"Could not assign public_short_code for order pk={order.pk}"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("industry", "0020_industryorderitem_targets"),
    ]

    operations = [
        migrations.AddField(
            model_name="industryorder",
            name="public_short_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="3-character public code (Discord); unique among active (unfulfilled) orders.",
                max_length=3,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            _backfill_public_short_codes, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="industryorder",
            name="public_short_code",
            field=models.CharField(
                db_index=True,
                help_text="3-character public code (Discord); unique among active (unfulfilled) orders.",
                max_length=3,
            ),
        ),
    ]
