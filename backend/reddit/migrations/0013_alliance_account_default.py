from django.db import migrations, models


def to_alliance_account(apps, schema_editor):
    """Every post was forced to a Discord reminder while automatic posting
    was off (0008, 0011). Posting as the alliance account is the default
    now; a CEO who wants reminders can pick them again."""
    RedditPostTemplate = apps.get_model("reddit", "RedditPostTemplate")
    moved = RedditPostTemplate.objects.filter(
        delivery_method="discord_reminder"
    ).update(delivery_method="alliance")
    print(f"\n  Moved {moved} Reddit posts to the alliance account")


def to_reminders(apps, schema_editor):
    RedditPostTemplate = apps.get_model("reddit", "RedditPostTemplate")
    RedditPostTemplate.objects.filter(delivery_method="alliance").update(
        delivery_method="discord_reminder"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("reddit", "0012_rotation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="redditposttemplate",
            name="delivery_method",
            field=models.CharField(
                choices=[
                    ("alliance", "Automatic post as the alliance account"),
                    ("automatic", "Automatic post from the CEO's account"),
                    ("discord_reminder", "Discord DM reminder"),
                ],
                default="alliance",
                max_length=20,
            ),
        ),
        migrations.RunPython(to_alliance_account, to_reminders),
    ]
