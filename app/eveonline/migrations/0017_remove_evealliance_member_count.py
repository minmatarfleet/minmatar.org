# Generated by Django 4.2.8 on 2023-12-18 02:33

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("eveonline", "0016_evegroup_unique_alter_evegroup_priority_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="evealliance",
            name="member_count",
        ),
    ]
