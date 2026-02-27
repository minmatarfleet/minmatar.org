from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("freight", "0010_evefreightroute_expiration_days_days_to_complete"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EveFreightContract",
        ),
    ]
