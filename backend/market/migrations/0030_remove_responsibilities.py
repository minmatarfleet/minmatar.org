# Generated manually for responsibility removal

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0029_contract_admin_indexes"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EveMarketContractResponsibility",
        ),
        migrations.DeleteModel(
            name="EveMarketItemResponsibility",
        ),
    ]
