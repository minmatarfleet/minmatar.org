from django.db import migrations


def normalize_expectation_quantities(apps, schema_editor):
    for model_name in (
        "EveMarketItemExpectation",
        "EveMarketFittingExpectation",
        "EveMarketContractExpectation",
    ):
        model = apps.get_model("market", model_name)
        model.objects.exclude(quantity=1).update(quantity=1)


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0039_health_snapshot_listed_targets"),
    ]

    operations = [
        migrations.RunPython(
            normalize_expectation_quantities,
            migrations.RunPython.noop,
        ),
    ]
