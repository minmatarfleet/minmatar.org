# Generated by Django 5.0.4 on 2024-04-16 17:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("esi", "0012_fix_token_type_choices"),
        ("eveonline", "0031_alter_evecharacter_alliance_and_more"),
        (
            "eveuniverse",
            "0010_alter_eveindustryactivityduration_eve_type_and_more",
        ),
    ]

    operations = [
        migrations.AddIndex(
            model_name="evecharacter",
            index=models.Index(
                fields=["character_name"],
                name="eveonline_e_charact_d47325_idx",
            ),
        ),
    ]
