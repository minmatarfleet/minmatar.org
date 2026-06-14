from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0014_discordchannel"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="DiscordVoiceMinuteRecord",
            new_name="DiscordChannelActivityRecord",
        ),
        migrations.RenameField(
            model_name="discordchannelactivityrecord",
            old_name="minutes",
            new_name="quantity",
        ),
        migrations.AddField(
            model_name="discordchannelactivityrecord",
            name="activity_type",
            field=models.CharField(
                choices=[
                    ("text_message", "Text message"),
                    ("voice_minute", "Voice minute"),
                ],
                default="voice_minute",
                max_length=32,
            ),
        ),
        migrations.AlterModelTable(
            name="discordchannelactivityrecord",
            table="discord_discordchannelactivityrecord",
        ),
        migrations.AddIndex(
            model_name="discordchannelactivityrecord",
            index=models.Index(
                fields=["activity_type", "created_on"],
                name="activity_type_created_on_idx",
            ),
        ),
    ]
