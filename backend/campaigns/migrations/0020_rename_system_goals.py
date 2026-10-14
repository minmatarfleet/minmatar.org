# Rename SystemGoal wire values to military terms.

from django.db import migrations, models

GOAL_REMAP = {
    "capture": "take",
    "defend": "hold",
    "contest": "pressure",
    "scout": "recon",
}

NEW_CHOICES = [
    ("take", "Take"),
    ("hold", "Hold"),
    ("pressure", "Pressure"),
    ("disrupt", "Disrupt"),
    ("recon", "Recon"),
    ("none", "No goal"),
]


def remap_goals(apps, schema_editor):
    CampaignSystem = apps.get_model("campaigns", "CampaignSystem")
    CampaignArea = apps.get_model("campaigns", "CampaignArea")
    for old, new in GOAL_REMAP.items():
        CampaignSystem.objects.filter(goal=old).update(goal=new)
        CampaignArea.objects.filter(goal=old).update(goal=new)


def unremap_goals(apps, schema_editor):
    reverse = {new: old for old, new in GOAL_REMAP.items()}
    CampaignSystem = apps.get_model("campaigns", "CampaignSystem")
    CampaignArea = apps.get_model("campaigns", "CampaignArea")
    for new, old in reverse.items():
        CampaignSystem.objects.filter(goal=new).update(goal=old)
        CampaignArea.objects.filter(goal=new).update(goal=old)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0019_theater_lookups_and_area_goals"),
    ]

    operations = [
        migrations.RunPython(remap_goals, unremap_goals),
        migrations.AlterField(
            model_name="campaignsystem",
            name="goal",
            field=models.CharField(
                choices=NEW_CHOICES,
                default="take",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="campaignarea",
            name="goal",
            field=models.CharField(
                choices=NEW_CHOICES,
                default="recon",
                help_text=(
                    "What members should do in this constellation or region."
                ),
                max_length=16,
            ),
        ),
    ]
