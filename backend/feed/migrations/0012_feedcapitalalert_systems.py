from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0011_feed_capital_alert"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedcapitalalert",
            name="systems",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="feedcapitalalert",
            name="composition",
            field=models.JSONField(default=dict),
        ),
    ]
