from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("freight", "0011_delete_evefreightcontract"),
        ("eveonline", "0086_add_corporation_wallet_journal"),
    ]

    operations = [
        migrations.CreateModel(
            name="FreightContract",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("eveonline.evecorporationcontract",),
        ),
    ]
