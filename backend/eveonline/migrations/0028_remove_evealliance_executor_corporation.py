# Generated by Django 4.2.10 on 2024-03-04 13:09

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("eveonline", "0027_remove_evecorporation_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="evealliance",
            name="executor_corporation",
        ),
    ]
