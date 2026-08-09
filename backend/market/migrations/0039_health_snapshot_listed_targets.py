from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0038_market_health_snapshots"),
    ]

    operations = [
        migrations.AddField(
            model_name="evemarkethealthsnapshot",
            name="listed_targets",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
