from django.db import migrations, models


def staging_delivers(apps, schema_editor):
    """Orders already deliver to the staging, so it keeps doing so."""
    EveLocation = apps.get_model("eveonline", "EveLocation")
    EveLocation.objects.filter(
        staging_active=True, deleted__isnull=True
    ).update(industry_delivery=True)


def no_delivery(apps, schema_editor):
    EveLocation = apps.get_model("eveonline", "EveLocation")
    EveLocation.objects.filter(industry_delivery=True).update(
        industry_delivery=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0116_eve_location_freight_route"),
    ]

    operations = [
        migrations.AddField(
            model_name="evelocation",
            name="industry_delivery",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Industry orders can deliver here.",
            ),
        ),
        migrations.AddField(
            model_name="evelocation",
            name="dock_access",
            field=models.JSONField(
                blank=True,
                db_default=[],
                default=list,
                help_text="Who can dock: a list of {kind: corporation|alliance, id, name, ticker}. Empty means anyone in the alliance.",
            ),
        ),
        migrations.RunPython(staging_delivers, no_delivery),
    ]
