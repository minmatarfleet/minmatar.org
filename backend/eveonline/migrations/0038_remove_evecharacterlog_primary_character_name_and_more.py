# Generated by Django 5.0.6 on 2024-06-09 21:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0037_evecharacterlog_eveprimarycharacterchangelog"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="evecharacterlog",
            name="primary_character_name",
        ),
        migrations.RemoveField(
            model_name="eveprimarycharacterchangelog",
            name="user",
        ),
        migrations.AddField(
            model_name="eveprimarycharacterchangelog",
            name="username",
            field=models.CharField(default="test", max_length=255),
            preserve_default=False,
        ),
    ]