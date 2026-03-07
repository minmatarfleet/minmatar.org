# Remove system_id and system_name from MiningUpgradeCompletion; sov_system is the source.

from django.db import migrations, models


def backfill_sov_system(apps, schema_editor):
    MiningUpgradeCompletion = apps.get_model(
        "industry", "MiningUpgradeCompletion"
    )
    SystemSovereigntyConfig = apps.get_model(
        "sovereignty", "SystemSovereigntyConfig"
    )
    for completion in MiningUpgradeCompletion.objects.filter(
        sov_system__isnull=True
    ):
        try:
            config = SystemSovereigntyConfig.objects.get(
                system_id=completion.system_id
            )
            completion.sov_system = config
            completion.save(update_fields=["sov_system"])
        except SystemSovereigntyConfig.DoesNotExist:
            pass  # leave null; migration will fail if any remain when we set null=False


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sovereignty", "0002_switch_to_evetype"),
        ("industry", "0017_miningupgradecompletion_sov_site"),
    ]

    operations = [
        migrations.RunPython(backfill_sov_system, noop),
        migrations.RemoveIndex(
            model_name="miningupgradecompletion",
            name="industry_mi_system__756d08_idx",
        ),
        migrations.RemoveField(
            model_name="miningupgradecompletion",
            name="system_id",
        ),
        migrations.RemoveField(
            model_name="miningupgradecompletion",
            name="system_name",
        ),
        migrations.AlterField(
            model_name="miningupgradecompletion",
            name="sov_system",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="mining_completions",
                to="sovereignty.systemsovereigntyconfig",
            ),
        ),
        migrations.AddIndex(
            model_name="miningupgradecompletion",
            index=models.Index(
                fields=["sov_system", "-completed_at"],
                name="industry_mi_sov_syst_comp_idx",
            ),
        ),
    ]
