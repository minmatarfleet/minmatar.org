# Generated manually — drop legacy slug; public_short_code is the public id.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("industry", "0021_industryorder_public_short_code"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="industryorder",
            name="order_identifier",
        ),
    ]
