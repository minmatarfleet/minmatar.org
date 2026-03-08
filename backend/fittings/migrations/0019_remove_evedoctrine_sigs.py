# Generated manually: remove EveDoctrine.sigs (SIGs replaced by tribes)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0018_remove_eve_fitting_tags"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="evedoctrine",
            name="sigs",
        ),
    ]
