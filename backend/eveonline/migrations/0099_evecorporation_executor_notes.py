from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0098_unique_active_staging_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="evecorporation",
            name="executor_notes",
            field=models.TextField(blank=True),
        ),
    ]
