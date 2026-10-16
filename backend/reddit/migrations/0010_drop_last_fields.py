import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0106_merge_fw_payout_corporation_profile"),
        ("reddit", "0009_post_templates"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="discord_channel_id_old",
        ),
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="last_post_at",
        ),
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="last_reddit_post_title",
        ),
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="last_reddit_post_url",
        ),
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="last_reminder_at",
        ),
        migrations.RemoveField(
            model_name="redditposttemplate",
            name="last_scheduled_on",
        ),
        migrations.AlterField(
            model_name="redditposttemplate",
            name="corporation",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reddit_post_template",
                to="eveonline.evecorporation",
            ),
        ),
        migrations.AlterField(
            model_name="redditposttemplate",
            name="posting_day",
            field=models.CharField(
                blank=True,
                choices=[
                    ("monday", "Monday"),
                    ("tuesday", "Tuesday"),
                    ("wednesday", "Wednesday"),
                    ("thursday", "Thursday"),
                    ("friday", "Friday"),
                    ("saturday", "Saturday"),
                    ("sunday", "Sunday"),
                ],
                help_text="Picked by the CEO. Blank means not scheduled.",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="redditposttemplate",
            name="subreddit",
            field=models.CharField(
                blank=True,
                default="evejobs",
                help_text="Leave blank to pause the post.",
                max_length=250,
            ),
        ),
    ]
