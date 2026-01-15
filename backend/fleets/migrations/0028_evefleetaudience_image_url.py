# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0027_remove_evefleetaudiencewebhook_audience_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefleetaudience",
            name="image_url",
            field=models.URLField(
                blank=True,
                help_text="URL to the image to display for this fleet audience",
                max_length=500,
                null=True,
            ),
        ),
    ]

