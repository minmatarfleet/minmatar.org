from django.db import migrations, models


def adopt_or_create_table(apps, schema_editor):
    table_name = "standingfleet_standingfleetvoicerecord"
    if table_name in schema_editor.connection.introspection.table_names():
        return

    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute("""
            CREATE TABLE standingfleet_standingfleetvoicerecord (
                id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                created_on datetime(6) NOT NULL,
                username varchar(255) NOT NULL,
                minutes integer NOT NULL
            )
            """)
        schema_editor.execute("""
            CREATE INDEX created_on_idx
            ON standingfleet_standingfleetvoicerecord (created_on)
            """)
        schema_editor.execute("""
            CREATE INDEX username_idx
            ON standingfleet_standingfleetvoicerecord (username)
            """)
        return

    schema_editor.execute("""
        CREATE TABLE standingfleet_standingfleetvoicerecord (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            created_on datetime NOT NULL,
            username varchar(255) NOT NULL,
            minutes integer NOT NULL
        )
        """)
    schema_editor.execute("""
        CREATE INDEX created_on_idx
        ON standingfleet_standingfleetvoicerecord (created_on)
        """)
    schema_editor.execute("""
        CREATE INDEX username_idx
        ON standingfleet_standingfleetvoicerecord (username)
        """)


class Migration(migrations.Migration):

    dependencies = [
        (
            "discord",
            "0011_discordrole_created_at_discordrole_updated_at_and_more",
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="DiscordVoiceMinuteRecord",
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
                            "created_on",
                            models.DateTimeField(auto_now_add=True),
                        ),
                        ("username", models.CharField(max_length=255)),
                        ("minutes", models.IntegerField()),
                    ],
                    options={
                        "db_table": "standingfleet_standingfleetvoicerecord",
                    },
                ),
                migrations.AddIndex(
                    model_name="discordvoiceminuterecord",
                    index=models.Index(
                        fields=["created_on"], name="created_on_idx"
                    ),
                ),
                migrations.AddIndex(
                    model_name="discordvoiceminuterecord",
                    index=models.Index(
                        fields=["username"], name="username_idx"
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    adopt_or_create_table,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
