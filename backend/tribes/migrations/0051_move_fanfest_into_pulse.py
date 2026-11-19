"""Make Fanfest a Pulse tribe group and keep every member.

Migration 0050 created a Fanfest tribe plus an Attendees group. Fanfest
is a group inside Pulse instead. The group row is reparented, so
memberships, characters, history, ranks, invitations and events stay.
Active members are added to the Pulse tribe role and removed from the
Fanfest tribe role. Discord is updated with the auth-group signals; a
failure leaves that pilot on the old role. ``manage.py
move_fanfest_into_pulse`` retries the same move.
"""

import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def move_fanfest(apps, schema_editor):
    # Tests build their own rows and call the helper. A test database has
    # no production Fanfest roster to move.
    if getattr(settings, "TESTING", False):
        return
    # pylint: disable-next=import-outside-toplevel
    from discord.client import DiscordClient  # noqa: PLC0415

    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.move_fanfest_into_pulse import (  # noqa: PLC0415
        move_fanfest_into_pulse,
    )

    client = None
    try:
        client = DiscordClient()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Fanfest move: Discord client unavailable")
    for line in move_fanfest_into_pulse(apps, discord_client=client):
        logger.info(line)


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0050_seed_fanfest_tribe"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("discord", "0027_corp_discord_strip_roles_on_leave"),
        ("eveonline", "0111_evelocation_freight_active_help_text"),
        ("posts", "0009_tribe_publishing"),
        ("fleets", "0063_invite_confidence"),
        ("industry", "0056_industryorder_provisional"),
        ("groups", "0027_drop_legacy_mumble_access_table"),
        ("help_tickets", "0003_category_code_help_text"),
    ]

    operations = [
        migrations.RunPython(move_fanfest, migrations.RunPython.noop),
    ]
