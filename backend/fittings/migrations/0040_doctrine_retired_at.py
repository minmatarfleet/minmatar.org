from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0039_doctrine_capitals_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="evedoctrine",
            name="retired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
