"""Merge Capital Production and Subcapital Production into Production.

Every membership, character and history row moves onto one group.
Capital Production and Subcapital Production become ranks. A pilot who
was in both keeps the capital rank. Discord role updates that fail are
retried with ``manage.py merge_production_groups``.
"""

import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def merge_production(apps, schema_editor):
    # Tests build their own rows and call the helper. A test database has
    # no production roster to merge.
    if getattr(settings, "TESTING", False):
        return
    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.merge_production_groups import (  # noqa: PLC0415
        merge_production_groups,
    )

    for line in merge_production_groups(apps):
        logger.info(line)


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0052_tribe_group_chief_seats"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("discord", "0027_corp_discord_strip_roles_on_leave"),
        ("eveonline", "0114_structure_browser"),
        ("posts", "0009_tribe_publishing"),
        ("fleets", "0063_invite_confidence"),
        ("industry", "0056_industryorder_provisional"),
        ("groups", "0027_drop_legacy_mumble_access_table"),
        ("help_tickets", "0003_category_code_help_text"),
        ("structures", "0021_structure_browser"),
        ("taskboard", "0003_discord_messages"),
    ]

    operations = [
        migrations.RunPython(merge_production, migrations.RunPython.noop),
    ]
