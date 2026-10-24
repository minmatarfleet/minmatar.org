import django.db.models.deletion
import django.utils.timezone
from datetime import datetime, timezone as dt_timezone
from django.db import migrations, models

# RedditScheduledPost becomes RedditPostTemplate (one per corporation), and
# what used to be its last_* fields becomes RedditPost rows, one per
# delivery. The old fields are dropped in 0010 once the rows exist.


def drop_posts_without_corporation(apps, schema_editor):
    # 0008 retired the alliance post; any added by hand since then have
    # nobody to remind and can't be kept once the corporation is required.
    RedditScheduledPost = apps.get_model("reddit", "RedditScheduledPost")
    orphans = RedditScheduledPost.objects.filter(corporation__isnull=True)
    for post in orphans:
        print(
            f"\n  Deleting Reddit post {post.pk} with no corporation: "
            f"{post.title!r}"
        )
    orphans.delete()


def copy_history_and_channels(apps, schema_editor):
    RedditPostTemplate = apps.get_model("reddit", "RedditPostTemplate")
    RedditPost = apps.get_model("reddit", "RedditPost")
    DiscordChannel = apps.get_model("discord", "DiscordChannel")

    for template in RedditPostTemplate.objects.all():
        for post in history_rows(template):
            RedditPost.objects.create(template=template, **post)

        if template.discord_channel_id_old:
            channel = DiscordChannel.objects.filter(
                channel_id=template.discord_channel_id_old
            ).first()
            if channel is None:
                print(
                    f"\n  Reddit post {template.pk}: Discord channel "
                    f"{template.discord_channel_id_old} isn't a registered "
                    "DiscordChannel; pick it again in the admin"
                )
            else:
                template.discord_channel = channel
                template.save(update_fields=["discord_channel"])


def history_rows(template) -> list[dict]:
    """RedditPost fields for what the last_* fields remember."""
    posted = {
        "status": "posted",
        "title": template.last_reddit_post_title or "",
        "reddit_url": template.last_reddit_post_url or "",
    }
    rows = []
    post_at = template.last_post_at
    reminder_at = template.last_reminder_at
    if template.last_scheduled_on:
        # The slot the scheduler last claimed. Recording it keeps the
        # scheduler from delivering this week's slot a second time.
        slot = datetime.combine(
            template.last_scheduled_on,
            template.posting_time,
            tzinfo=dt_timezone.utc,
        )
        row = {"scheduled_for": slot, "status": "skipped", "created_at": slot}
        if post_at and post_at >= slot:
            row.update(posted, created_at=post_at)
            post_at = None
        elif reminder_at and reminder_at >= slot:
            row.update(status="reminded", created_at=reminder_at)
            reminder_at = None
        rows.append(row)
    if post_at:
        rows.append({**posted, "created_at": post_at})
    if reminder_at:
        rows.append({"status": "reminded", "created_at": reminder_at})
    return rows


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0022_discordchannel_receive_buyback"),
        ("eveonline", "0106_merge_fw_payout_corporation_profile"),
        ("reddit", "0008_reminder_only_and_drop_alliance_posts"),
    ]

    operations = [
        migrations.RunPython(
            drop_posts_without_corporation, migrations.RunPython.noop
        ),
        migrations.RenameModel(
            old_name="RedditScheduledPost",
            new_name="RedditPostTemplate",
        ),
        # The bare ID moves aside so the foreign key can take the name.
        migrations.RenameField(
            model_name="redditposttemplate",
            old_name="discord_channel_id",
            new_name="discord_channel_id_old",
        ),
        migrations.AddField(
            model_name="redditposttemplate",
            name="discord_channel",
            field=models.ForeignKey(
                blank=True,
                help_text="Text channel that gets a link after each Reddit post.",
                limit_choices_to={"channel_type": "text"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="discord.discordchannel",
            ),
        ),
        migrations.CreateModel(
            name="RedditPost",
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
                (
                    "scheduled_for",
                    models.DateTimeField(
                        blank=True,
                        help_text="The slot this was for. Blank when submitted by hand.",
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("posted", "Posted to Reddit"),
                            ("reminded", "CEO reminded on Discord"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="pending",
                        max_length=12,
                    ),
                ),
                (
                    "fallback_reason",
                    models.CharField(
                        blank=True,
                        help_text="Why an automatic post went out as a reminder instead.",
                        max_length=32,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        help_text="The title as sent.",
                        max_length=300,
                    ),
                ),
                (
                    "reddit_url",
                    models.URLField(blank=True, max_length=500),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="posts",
                        to="reddit.redditposttemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "scheduled_for"),
                        name="reddit_post_one_per_slot",
                    )
                ],
            },
        ),
        migrations.RunPython(
            copy_history_and_channels, migrations.RunPython.noop
        ),
    ]
