"""Adding TokenType.CAMPAIGN widens this field's choices.

Choices are not enforced by the database, so this only keeps the migration
state honest about the new campaign token type.
"""

from django.db import migrations, models

import tribes.models.tribe_group


class Migration(migrations.Migration):
    dependencies = [
        ("tribes", "0038_seed_fishermen_external_guild"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tribegroup",
            name="required_token_type",
            field=models.CharField(
                blank=True,
                choices=tribes.models.tribe_group.TribeGroup.TOKEN_TYPE_CHOICES,
                default="",
                help_text=(
                    "If set, characters must have this ESI token type to "
                    "apply or be added."
                ),
                max_length=40,
            ),
        ),
    ]
