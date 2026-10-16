from django.db import migrations

# For the time being every post goes out as a Discord reminder to the CEO, and
# the alliance post (no corporation, so nobody to remind) is retired. Rows are
# logged so the deploy output keeps a record of what was removed.


def reminder_only(apps, schema_editor):
    RedditScheduledPost = apps.get_model("reddit", "RedditScheduledPost")
    alliance_posts = RedditScheduledPost.objects.filter(
        corporation__isnull=True
    )
    for post in alliance_posts:
        print(
            f"\n  Deleting alliance Reddit post {post.pk}: {post.title!r} "
            f"(r/{post.subreddit}, {post.posting_day or 'unscheduled'})"
        )
    alliance_posts.delete()
    flipped = RedditScheduledPost.objects.exclude(
        delivery_method="discord_reminder"
    ).update(delivery_method="discord_reminder")
    if flipped:
        print(f"\n  Switched {flipped} Reddit post(s) to Discord reminder")


class Migration(migrations.Migration):

    dependencies = [
        ("reddit", "0007_corporation_settings"),
    ]

    operations = [
        # Not reversible in data terms: deleted posts aren't restored.
        migrations.RunPython(reminder_only, migrations.RunPython.noop),
    ]
