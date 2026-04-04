from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0019_remove_evedoctrine_sigs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evefitting",
            name="name",
            field=models.CharField(max_length=255),
        ),
    ]
