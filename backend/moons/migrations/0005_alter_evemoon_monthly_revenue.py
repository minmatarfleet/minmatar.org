# Generated by Django 5.0.8 on 2024-10-09 13:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("moons", "0004_evemoon_monthly_revenue"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evemoon",
            name="monthly_revenue",
            field=models.BigIntegerField(default=0),
        ),
    ]
