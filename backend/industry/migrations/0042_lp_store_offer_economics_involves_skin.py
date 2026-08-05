# Generated manually for involves_skin on LP offer economics snapshot.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0041_lp_store_offer_economics"),
    ]

    operations = [
        migrations.AddField(
            model_name="industrylpstoreoffereconomics",
            name="involves_skin",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
