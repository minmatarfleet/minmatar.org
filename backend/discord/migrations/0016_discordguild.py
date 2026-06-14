from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0015_discordchannelactivityrecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscordGuild",
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
                ("guild_id", models.BigIntegerField(unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "is_primary",
                    models.BooleanField(
                        default=False,
                        help_text="Matches DISCORD_GUILD_ID in application settings.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Bot was present in this guild on the last sync.",
                    ),
                ),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
