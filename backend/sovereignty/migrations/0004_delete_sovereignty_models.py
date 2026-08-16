# Remove sovereignty tracking models (experimental; mining FK already dropped).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sovereignty", "0003_alter_systemsovereigntyconfig_options"),
        ("industry", "0046_delete_miningupgradecompletion"),
    ]

    operations = [
        migrations.DeleteModel(name="SystemSovereigntyUpgrade"),
        migrations.DeleteModel(name="SystemBaseResources"),
        migrations.DeleteModel(name="SystemSovereigntyConfig"),
    ]
