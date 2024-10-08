# Generated by Django 5.0.4 on 2024-04-13 13:51

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0010_affiliationtype_default_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="sig",
            name="members",
            field=models.ManyToManyField(
                blank=True, related_name="sigs", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name="sig",
            name="officers",
            field=models.ManyToManyField(
                blank=True,
                related_name="officer_of",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="directors",
            field=models.ManyToManyField(
                blank=True,
                related_name="director_of",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="members",
            field=models.ManyToManyField(
                blank=True, related_name="teams", to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
