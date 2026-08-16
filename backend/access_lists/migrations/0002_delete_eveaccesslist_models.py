# Remove EveAccessList / EveAccessListMember (dead experimental feature).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("access_lists", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="EveAccessListMember"),
        migrations.DeleteModel(name="EveAccessList"),
    ]
