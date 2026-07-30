# Generated manually for Amarr fleet Discord pings

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0012_feedcapitalalert_systems"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeedAmarrFleetAlert",
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
                ("solar_system_id", models.BigIntegerField(db_index=True)),
                ("system_name", models.CharField(max_length=64)),
                ("systems", models.JSONField(default=list)),
                ("title", models.CharField(max_length=256)),
                (
                    "subheader",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                ("preview", models.TextField(blank=True, default="")),
                ("kills", models.PositiveIntegerField(default=0)),
                ("pilots", models.PositiveIntegerField(default=0)),
                ("roster", models.JSONField(default=list)),
                ("roster_total", models.PositiveIntegerField(default=0)),
                (
                    "cluster_key",
                    models.CharField(db_index=True, max_length=256),
                ),
                ("discord_messages", models.JSONField(default=list)),
                ("last_activity_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-last_activity_at"],
            },
        ),
        migrations.CreateModel(
            name="FeedAmarrFleetPing",
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
                    "cluster_key",
                    models.CharField(
                        db_index=True, max_length=256, unique=True
                    ),
                ),
                ("solar_system_id", models.BigIntegerField()),
                (
                    "discord_message_id",
                    models.BigIntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "alert",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pings",
                        to="feed.feedamarrfleetalert",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
