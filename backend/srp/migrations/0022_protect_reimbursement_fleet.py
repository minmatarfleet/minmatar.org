# Django enforces on_delete in Python, so this changes no database schema.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0049_fleet_fitting_utility_role"),
        ("srp", "0021_podreimbursementprogram_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evefleetshipreimbursement",
            name="fleet",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reimbursements",
                to="fleets.evefleet",
            ),
        ),
    ]
