# Generated manually for campaign FK on EvePost.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0012_campaign_kinds_and_structures"),
        ("posts", "0007_evepost_tribe_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="evepost",
            name="campaign",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Optional campaign this post (propaganda, write-up) is for."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posts",
                to="campaigns.campaign",
            ),
        ),
    ]
