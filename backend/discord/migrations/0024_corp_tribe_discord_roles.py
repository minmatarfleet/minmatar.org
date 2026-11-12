from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0023_discordchannel_receive_lp_conversion_alerts"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordguild",
            name="can_manage_roles",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="discordguild",
            name="roles_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discordguild",
            name="roles",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="DiscordRoleMapping",
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
                    "state",
                    models.CharField(
                        choices=[
                            ("member", "Member"),
                            ("director", "Director"),
                            ("recruiter", "Recruiter"),
                            ("structure_manager", "Structure manager"),
                            ("alliance_member", "Alliance member"),
                        ],
                        max_length=32,
                    ),
                ),
                ("role_id", models.BigIntegerField()),
                (
                    "problem",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "guild",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="role_mappings",
                        to="discord.discordguild",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="discordrolemapping",
            constraint=models.UniqueConstraint(
                fields=("guild", "state"),
                name="discord_role_mapping_guild_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="discordrolemapping",
            constraint=models.UniqueConstraint(
                fields=("guild", "role_id"),
                name="discord_role_mapping_guild_role",
            ),
        ),
    ]
