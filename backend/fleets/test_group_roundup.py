"""The daily roundup of a group's fleets (docs/tribes/group-fleet-roundup.md)."""

from datetime import date, datetime, timezone as dt_timezone

from django.db.models import signals
from django.test import override_settings

from app.links import fleet_url
from app.test import TestCase
from fleets.endpoints.helpers import SILENT_MESSAGE_FLAG
from fleets.helpers.group_roundup import (
    ROUNDUP_DAYS,
    build_roundup_payload,
    roundup_fleets,
)
from fleets.models import EveFleet
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)

TODAY = date(2026, 12, 1)  # a Tuesday


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A UTC (EVE) time ``day`` days after TODAY."""
    return datetime(2026, 12, 1 + day, hour, minute, tzinfo=dt_timezone.utc)


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )


def tearDownModule():
    # pylint: disable-next=import-outside-toplevel
    from fleets.signals import update_fleet_schedule_on_save

    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )


@override_settings(
    DISCORD_FLEET_EMOJIS={"non_strategic": {"name": "ns", "id": 42}}
)
class GroupRoundupTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group(name="Mining", code="industry.mining")
        self.fc = make_user("miner_fc", character_name="Keldar")
        add_member(self.group, self.fc)

    def fleet(self, start, **fields) -> EveFleet:
        values = {
            "type": "non_strategic",
            "description": "Mining op",
            "start_time": start,
            "created_by": self.fc,
            "host_group": self.group,
            "status": "pending",
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def test_window_is_tomorrow_through_day_five(self):
        self.assertEqual(ROUNDUP_DAYS, 5)
        self.fleet(at(0, 23))
        first = self.fleet(at(1, 0))
        last = self.fleet(at(5, 23, 59))
        self.fleet(at(6, 0))
        self.assertEqual(roundup_fleets(self.group, TODAY), [first, last])

    def test_excludes_cancelled_private_and_campaign(self):
        kept = self.fleet(at(2, 18))
        self.fleet(at(2, 19), status="cancelled")
        self.fleet(at(2, 20), invite_only=True)
        self.fleet(at(2, 21), type="standing")
        self.fleet(at(2, 22), type="gang")
        self.assertEqual(roundup_fleets(self.group, TODAY), [kept])

    def test_other_groups_fleets_excluded(self):
        other = make_tribe_group(
            name="Dreads", code="capitals.dreads", role_id=None
        )
        self.fleet(at(2, 18), host_group=other)
        self.fleet(at(2, 18), host_group=None)
        self.assertEqual(roundup_fleets(self.group, TODAY), [])

    def test_no_fleets_is_none(self):
        self.assertIsNone(build_roundup_payload(self.group, [], TODAY))

    def test_days_grouped_tomorrow_first(self):
        first = self.fleet(at(1, 18), objective="Gukarla moon belt")
        second = self.fleet(at(2, 19), objective="Amo ice")
        payload = build_roundup_payload(self.group, [first, second], TODAY)
        ts1 = int(at(1, 18).timestamp())
        ts2 = int(at(2, 19).timestamp())
        lead = "- <:ns:42> "
        self.assertEqual(
            payload["content"],
            "### Mining fleets — next 5 days\n"
            "**Tomorrow, Wed 2 Dec**\n"
            f"{lead}18:00 EVE (<t:{ts1}:t>) Keldar · Gukarla moon belt · "
            f"[Fleet](<{fleet_url(first.id)}>)\n"
            "**Thu 3 Dec**\n"
            f"{lead}19:00 EVE (<t:{ts2}:t>) Keldar · Amo ice · "
            f"[Fleet](<{fleet_url(second.id)}>)\n"
            "-# Sign up on the fleet page.",
        )

    def test_silent_flags(self):
        payload = build_roundup_payload(
            self.group, [self.fleet(at(1, 18))], TODAY
        )
        self.assertEqual(payload["flags"], SILENT_MESSAGE_FLAG)
        self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_fleet_without_fc_or_title(self):
        fleet = self.fleet(at(1, 18), created_by=None, objective="")
        content = build_roundup_payload(self.group, [fleet], TODAY)["content"]
        ts = int(at(1, 18).timestamp())
        self.assertIn(f"18:00 EVE (<t:{ts}:t>) · [Fleet](<", content)

    def test_long_week_truncates_under_2000(self):
        fleets = [
            self.fleet(at(1 + i % 5, i % 24), objective="x" * 40)
            for i in range(40)
        ]
        fleets.sort(key=lambda f: f.start_time)
        content = build_roundup_payload(self.group, fleets, TODAY)["content"]
        self.assertLessEqual(len(content), 2000)
        self.assertRegex(
            content, r"…and \d+ more\n-# Sign up on the fleet page\.$"
        )
