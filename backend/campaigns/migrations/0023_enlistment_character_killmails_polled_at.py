from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0022_campaign_parties"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaignenlistmentcharacter",
            name="killmails_polled_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Drives the recent-killmail polling rotation.",
                null=True,
            ),
        ),
    ]
