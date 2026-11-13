from django.db import migrations, models


def existing_policies_remove(apps, schema_editor):
    # Before this, a member policy always removed people.
    DiscordGuild = apps.get_model("discord", "DiscordGuild")
    DiscordGuild.objects.exclude(member_policy="").update(
        member_action="remove"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0025_corp_discord_member_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordguild",
            name="member_action",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Leave them"),
                    ("notify", "Tell the CEO"),
                    ("remove", "Remove them"),
                ],
                db_default="",
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="discordguildremoval",
            name="notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            existing_policies_remove, migrations.RunPython.noop
        ),
    ]
