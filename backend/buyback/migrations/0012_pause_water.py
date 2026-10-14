from django.db import migrations


def pause_water(apps, schema_editor):
    Accepted = apps.get_model("buyback", "BuybackAcceptedItem")
    EveType = apps.get_model("eveuniverse", "EveType")
    type_ids = list(
        EveType.objects.filter(name="Water").values_list("id", flat=True)
    )
    if not type_ids:
        return
    Accepted.objects.filter(eve_type_id__in=type_ids).update(active=False)


def unpause_water(apps, schema_editor):
    Accepted = apps.get_model("buyback", "BuybackAcceptedItem")
    EveType = apps.get_model("eveuniverse", "EveType")
    type_ids = list(
        EveType.objects.filter(name="Water").values_list("id", flat=True)
    )
    if not type_ids:
        return
    Accepted.objects.filter(eve_type_id__in=type_ids).update(active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0011_settings_coordinators"),
    ]

    operations = [
        migrations.RunPython(pause_water, unpause_water),
    ]
