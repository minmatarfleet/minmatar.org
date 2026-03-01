from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0009_remove_group_requirement"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tribegrouprequirement",
            name="requirement_type",
        ),
    ]
