import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Rows that exist before this migration are alliance posts that the
# scheduler already submits automatically from the alliance account. They are
# added as automatic and approved so nothing about them changes; the model
# defaults (Discord reminder, not approved) apply to new rows only.
APPROVED_FIELD = models.BooleanField(
    default=False,
    help_text="Superuser approval for automatic posting. Cleared when the CEO edits the title or content.",
)
DELIVERY_FIELD = models.CharField(
    choices=[
        ("discord_reminder", "Discord DM reminder"),
        ("automatic", "Automatic post"),
    ],
    default="discord_reminder",
    max_length=20,
)


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0106_merge_fw_payout_corporation_profile"),
        ("reddit", "0006_remove_redditscheduledpost_discord_channel_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="redditscheduledpost",
            name="approved",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="redditscheduledpost",
            name="approved",
            field=APPROVED_FIELD,
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="corporation",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reddit_post",
                to="eveonline.evecorporation",
            ),
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="delivery_method",
            field=models.CharField(default="automatic", max_length=20),
        ),
        migrations.AlterField(
            model_name="redditscheduledpost",
            name="delivery_method",
            field=DELIVERY_FIELD,
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="last_reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="last_scheduled_on",
            field=models.DateField(
                blank=True,
                help_text="Day the scheduler last handled this post (one run per day).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="redditscheduledpost",
            name="posting_time",
            field=models.TimeField(
                default=datetime.time(13, 0),
                help_text="EVE time (UTC). Posts go out within 15 minutes of this.",
            ),
        ),
        migrations.AlterField(
            model_name="redditscheduledpost",
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
                help_text="Leave blank to keep a corporation draft unscheduled.",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="redditscheduledpost",
            name="subreddit",
            field=models.CharField(
                blank=True,
                help_text="Leave blank to keep a corporation draft unscheduled.",
                max_length=250,
            ),
        ),
        migrations.CreateModel(
            name="RedditAccount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reddit_username", models.CharField(max_length=64)),
                ("refresh_token", models.TextField()),
                ("scopes", models.JSONField(blank=True, default=list)),
                (
                    "token_invalid",
                    models.BooleanField(
                        default=False,
                        help_text="Reddit rejected the refresh token; the user must reconnect.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reddit_account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
