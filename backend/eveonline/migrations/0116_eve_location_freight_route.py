from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0115_eve_location_deployment"),
    ]

    operations = [
        migrations.AddField(
            model_name="evelocation",
            name="freight_route_active",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="On a freight run but not a delivery point, such as a midpoint or an office. Shown as a Freight route tag; routes are not touched.",
            ),
        ),
    ]
