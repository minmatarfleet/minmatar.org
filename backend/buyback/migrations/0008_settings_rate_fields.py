"""Buyback rate fields: demand / surplus / ore refine as first-class columns."""

import buyback.models
from django.db import migrations, models


def _float_or_none(raw, key):
    if not isinstance(raw, dict) or key not in raw or raw[key] is None:
        return None
    try:
        return float(raw[key])
    except (TypeError, ValueError):
        return None


def forwards_copy_rate_rules(apps, schema_editor):
    EveBuybackSettings = apps.get_model("buyback", "EveBuybackSettings")
    for settings in EveBuybackSettings.objects.all():
        raw = (
            settings.rate_rules
            if isinstance(settings.rate_rules, dict)
            else {}
        )
        demand = _float_or_none(raw, "demand_jita_buy")
        if demand is None:
            demand = _float_or_none(raw, "other_jita_buy")
        surplus = _float_or_none(raw, "surplus_jita_buy")
        if surplus is None:
            surplus = _float_or_none(raw, "p1_jita_buy_cap")
        ore = _float_or_none(raw, "ore_refine")

        if demand is not None:
            settings.demand_jita_buy = demand
        if surplus is not None:
            settings.surplus_jita_buy = surplus
        if ore is not None:
            settings.ore_refine = ore
        settings.rate_rules = {
            "ore_refine": float(settings.ore_refine),
            "demand_jita_buy": float(settings.demand_jita_buy),
            "surplus_jita_buy": float(settings.surplus_jita_buy),
        }
        settings.save(
            update_fields=[
                "demand_jita_buy",
                "surplus_jita_buy",
                "ore_refine",
                "rate_rules",
            ]
        )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("buyback", "0007_update_leading_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="evebuybacksettings",
            name="demand_jita_buy",
            field=models.FloatField(
                default=1.0,
                help_text="Share of Jita buy paid for in-demand items (1.0 = 100%).",
            ),
        ),
        migrations.AddField(
            model_name="evebuybacksettings",
            name="surplus_jita_buy",
            field=models.FloatField(
                default=0.9,
                help_text="Share of Jita buy paid for surplus accepted items.",
            ),
        ),
        migrations.AddField(
            model_name="evebuybacksettings",
            name="ore_refine",
            field=models.FloatField(
                default=0.85,
                help_text="Assumed refine yield for compressed ore pricing.",
            ),
        ),
        migrations.RunPython(forwards_copy_rate_rules, backwards_noop),
        migrations.AlterField(
            model_name="evebuybacksettings",
            name="rate_rules",
            field=models.JSONField(
                blank=True,
                default=buyback.models._default_rate_rules,
            ),
        ),
    ]
