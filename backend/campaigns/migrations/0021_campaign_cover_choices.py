# Curated cover_image_url choices for the Story tab picker.

from django.db import migrations, models

COVER_CHOICES = [
    ("", "Default (by campaign kind)"),
    ("/images/home-auga-cover.jpg", "Auga"),
    ("/images/home-amamake-cover.jpg", "Amamake"),
    ("/images/home-cover-og.jpg", "Watermellon"),
    ("/images/home-vard-cover.jpg", "Vard"),
    ("/images/home-evati-cover.jpg", "Evati"),
    ("/images/home-nakah-cover.jpg", "Nakah"),
    ("/images/home-r6-2-cover.jpg", "R-6KYM"),
    ("/images/home-amarr-cover.jpg", "Amarr"),
    ("/images/warzone-card.jpg", "Warzone card"),
    ("/images/warzone-cover.jpg", "Warzone"),
    ("/images/etherium-campaign.webp", "Etherium Reach"),
    ("/images/providence-campaign.webp", "Providence"),
    ("/images/scalding-campaign.webp", "Scalding Pass"),
    ("/images/hek-campaign.webp", "Hek"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0020_rename_system_goals"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campaign",
            name="cover_image_url",
            field=models.CharField(
                blank=True,
                choices=COVER_CHOICES,
                default="",
                help_text=(
                    "Pick from the site cover gallery. Leave default to use "
                    "the kind fallback on the campaign card."
                ),
                max_length=512,
            ),
        ),
    ]
