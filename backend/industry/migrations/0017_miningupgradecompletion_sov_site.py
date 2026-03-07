# MiningUpgradeCompletion: add sov_system FK and site_name for respawn lookup

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sovereignty", "0002_switch_to_evetype"),
        (
            "industry",
            "0016_rename_industry_mi_system__a2c8b4_idx_industry_mi_system__756d08_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="miningupgradecompletion",
            name="sov_system",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mining_completions",
                to="sovereignty.systemsovereigntyconfig",
            ),
        ),
        migrations.AddField(
            model_name="miningupgradecompletion",
            name="site_name",
            field=models.CharField(
                blank=True,
                help_text="Anomaly/site name (e.g. Large Veldspar Deposit) for respawn lookup.",
                max_length=255,
            ),
        ),
    ]
