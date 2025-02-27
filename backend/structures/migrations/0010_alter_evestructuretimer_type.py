# Generated by Django 5.1.2 on 2025-01-23 22:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0009_alter_evestructuretimer_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evestructuretimer",
            name="type",
            field=models.CharField(
                choices=[
                    ("astrahus", "Astrahus"),
                    ("fortizar", "Fortizar"),
                    ("keepstar", "Keepstar"),
                    ("raitaru", "Raitaru"),
                    ("azbel", "Azbel"),
                    ("sotiyo", "Sotiyo"),
                    ("athanor", "Athanor"),
                    ("tatara", "Tatara"),
                    ("tenebrex_cyno_jammer", "Tenebrex Cyno Jammer"),
                    ("pharolux_cyno_beacon", "Pharolux Cyno Beacon"),
                    ("ansiblex_jump_gate", "Ansiblex Jump Gate"),
                    ("orbital_skyhook", "Orbital Skyhook"),
                    ("metenox_moon_drill", "Metenox Moon Drill"),
                    (
                        "player_owned_customs_office",
                        "Player Owned Customs Office",
                    ),
                    ("player_owned_starbase", "Player Owned Starbase"),
                    ("mercenary_den", "Mercenary Den"),
                ],
                max_length=255,
            ),
        ),
    ]
