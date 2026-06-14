from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0013_discordvoiceminuterecord_channel_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscordChannel",
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
                ("channel_id", models.BigIntegerField(unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "channel_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("voice", "Voice"),
                            ("stage", "Stage"),
                            ("forum", "Forum"),
                            ("category", "Category"),
                            ("unknown", "Unknown"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "track_voice_activity",
                    models.BooleanField(
                        default=False,
                        help_text="When enabled, the bot records voice presence in this channel each minute.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
