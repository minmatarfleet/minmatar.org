# Optional auth group link on tribe group ranks (synced via membership signal).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("tribes", "0026_tribegrouprank_membership_rank"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribegrouprank",
            name="group",
            field=models.OneToOneField(
                blank=True,
                help_text="Auth group applied when a member holds this rank (e.g. Strategic FC).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tribe_group_rank",
                to="auth.group",
            ),
        ),
    ]
