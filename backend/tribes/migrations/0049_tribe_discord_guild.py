from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0024_corp_tribe_discord_roles"),
        ("tribes", "0048_delete_advocates_tribe_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribe",
            name="discord_guild",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="tribes",
                to="discord.discordguild",
            ),
        ),
    ]
