# Opponents → Parties (kind + enemy/ally side).

import django.db.models.deletion
from django.db import migrations, models


def copy_opponents_to_parties(apps, schema_editor):
    CampaignOpponent = apps.get_model("campaigns", "CampaignOpponent")
    CampaignParty = apps.get_model("campaigns", "CampaignParty")
    for row in CampaignOpponent.objects.all().iterator():
        if row.alliance_id:
            kind = "alliance"
        elif row.corporation_id:
            kind = "corporation"
        elif row.faction_id:
            kind = "faction"
        else:
            kind = "alliance"
        CampaignParty.objects.create(
            campaign_id=row.campaign_id,
            kind=kind,
            side="enemy",
            character_id=None,
            corporation_id=row.corporation_id,
            alliance_id=row.alliance_id,
            faction_id=row.faction_id,
            name=row.name,
            ticker=row.ticker or "",
            created_at=row.created_at,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0021_campaign_cover_choices"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignParty",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("character", "Character"),
                            ("corporation", "Corporation"),
                            ("alliance", "Alliance"),
                            ("faction", "Faction"),
                        ],
                        db_index=True,
                        default="alliance",
                        max_length=16,
                    ),
                ),
                (
                    "side",
                    models.CharField(
                        choices=[
                            ("enemy", "Enemy"),
                            ("ally", "Ally"),
                        ],
                        db_index=True,
                        default="enemy",
                        max_length=8,
                    ),
                ),
                (
                    "character_id",
                    models.BigIntegerField(
                        blank=True, db_index=True, null=True
                    ),
                ),
                (
                    "corporation_id",
                    models.BigIntegerField(
                        blank=True, db_index=True, null=True
                    ),
                ),
                (
                    "alliance_id",
                    models.BigIntegerField(
                        blank=True, db_index=True, null=True
                    ),
                ),
                (
                    "faction_id",
                    models.IntegerField(blank=True, db_index=True, null=True),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "ticker",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parties",
                        to="campaigns.campaign",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "parties",
                "ordering": ["side", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="campaignparty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("alliance_id__isnull", False)),
                fields=("campaign", "alliance_id"),
                name="campaign_party_alliance_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignparty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("corporation_id__isnull", False)),
                fields=("campaign", "corporation_id"),
                name="campaign_party_corporation_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignparty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("character_id__isnull", False)),
                fields=("campaign", "character_id"),
                name="campaign_party_character_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignparty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("faction_id__isnull", False)),
                fields=("campaign", "faction_id"),
                name="campaign_party_faction_unique",
            ),
        ),
        migrations.RunPython(copy_opponents_to_parties, noop_reverse),
        migrations.DeleteModel(name="CampaignOpponent"),
        migrations.AlterField(
            model_name="campaignstructure",
            name="related_alliance_id",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                help_text=(
                    "Affiliated alliance when the legal owner is an alt corp "
                    "(e.g. CVA). Used with campaign parties for "
                    "hostile/friendly."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="campaignstructure",
            name="related_alliance_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Scout-entered affiliated alliance name.",
                max_length=255,
            ),
        ),
    ]
