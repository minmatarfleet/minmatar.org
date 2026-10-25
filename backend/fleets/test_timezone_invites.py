"""Fleet invites follow the fleet time: group, corporation and new pilot
picks only reach pilots who play then (docs/fleets/private-fleets.md)."""

from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporation
from fleets.helpers.private_fleets import PrivateFleetError, send_wave
from fleets.models import EveFleetInvite
from fleets.test_standard_fleet_invites import (
    StandardInviteTestBase,
    _onboarding_snapshot,
)
from timezones.models import PilotTimezone
from tribes.tests.publishing_fixtures import add_member, make_user

# Sat 01:00 EVE: US evening and EU late night.
US_EVENING = datetime(2030, 11, 2, 1, tzinfo=dt_timezone.utc)
# Sat 20:00 EVE: EU evening only.
EU_EVENING = datetime(2030, 11, 2, 20, tzinfo=dt_timezone.utc)


def set_timezone(user, *brackets, source="activity"):
    now = timezone.now()
    PilotTimezone.objects.update_or_create(
        user=user,
        defaults={
            "brackets": list(brackets),
            "home": brackets[0][:2] if brackets else None,
            "home_source": source if brackets else None,
            "assessed_at": now,
            "changed_at": now,
        },
    )


class TimezoneInviteTestBase(StandardInviteTestBase):
    def setUp(self):
        super().setUp()
        # self.group holds pilot and no_discord; add an EU and an unknown.
        self.eu = make_user("eu", character_name="Treges")
        self.unknown = make_user("unknown", character_name="Teyn")
        add_member(self.group, self.eu)
        add_member(self.group, self.unknown)
        set_timezone(self.pilot, "USTZ")
        set_timezone(self.no_discord, "USTZ", "USTZ+")
        set_timezone(self.eu, "EUTZ")

    def preview(self, fleet, user=None, **body):
        response = self.call(
            "post", f"/{fleet.id}/invites/preview", user or self.fc, body
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()


class FleetTimeTests(TimezoneInviteTestBase):
    def test_tab_says_which_timezones_play_at_the_fleet_time(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        body = self.call("get", f"/{fleet.id}/invites", self.fc).json()
        self.assertEqual(body["fleet_timezones"], ["USTZ", "EUTZ+"])
        self.assertFalse(body["timezones_nearest"])
        self.assertFalse(body["can_choose_timezones"])

    def test_group_pick_leaves_out_other_timezones(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        preview = self.preview(fleet, tribe_group_ids=[self.group.id])
        self.assertEqual(preview["picked"], 4)
        self.assertEqual(preview["other_timezones"], 1)
        self.assertEqual(
            preview["other_timezones_by_bracket"],
            [{"code": "EUTZ", "count": 1}],
        )
        # pilot, no_discord and unknown are left: two with Discord.
        self.assertEqual(preview["new"], 3)
        self.assertEqual(
            preview["picks"],
            [
                {
                    "kind": "tribe_group",
                    "id": self.group.id,
                    "total": 4,
                    "in_timezone": 3,
                }
            ],
        )

    def test_a_named_pilot_is_always_invited(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        preview = self.preview(
            fleet, tribe_group_ids=[self.group.id], user_ids=[self.eu.id]
        )
        self.assertEqual(preview["other_timezones"], 0)
        self.assertEqual(preview["new"], 4)

    def test_unticking_a_timezone_narrows_the_pick(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        set_timezone(self.eu, "EUTZ", "EUTZ+")
        both = self.preview(fleet, tribe_group_ids=[self.group.id])
        self.assertEqual(both["other_timezones"], 0)
        us_only = self.preview(
            fleet, tribe_group_ids=[self.group.id], timezones=["USTZ"]
        )
        self.assertEqual(us_only["other_timezones"], 1)

    def test_a_standard_fc_cannot_add_other_timezones(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        for asked in (["EUTZ"], ["any"], []):
            preview = self.preview(
                fleet, tribe_group_ids=[self.group.id], timezones=asked
            )
            self.assertEqual(preview["other_timezones"], 1, asked)

    def test_the_send_skips_other_timezones(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        send_wave(
            fleet,
            sent_by=self.fc,
            tribe_group_ids=[self.group.id],
            timezones=["USTZ", "EUTZ+"],
        )
        invited = set(
            EveFleetInvite.objects.filter(eve_fleet=fleet).values_list(
                "user_id", flat=True
            )
        )
        self.assertEqual(
            invited, {self.pilot.id, self.no_discord.id, self.unknown.id}
        )

    def test_a_send_with_only_other_timezones_says_so(self):
        fleet = self.standard_fleet(start_time=EU_EVENING)
        for user in (self.eu, self.unknown):
            set_timezone(user, "USTZ")
        with self.assertRaisesMessage(PrivateFleetError, "fleet time"):
            send_wave(
                fleet,
                sent_by=self.fc,
                tribe_group_ids=[self.group.id],
                timezones=["EUTZ"],
            )

    def test_new_pilot_rows_count_the_fleet_time(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        _onboarding_snapshot(
            first_week=[self.pilot, self.eu, self.unknown],
            more_fleets=[self.outsider],
        )
        body = self.call("get", f"/{fleet.id}/invites", self.fc).json()
        self.assertEqual(body["onboarding_first_week"], 3)
        self.assertEqual(body["onboarding_first_week_in_timezone"], 2)
        self.assertEqual(body["onboarding_more_fleets_in_timezone"], 1)
        preview = self.preview(fleet, onboarding=["first_week"])
        self.assertEqual(preview["other_timezones"], 1)
        self.assertEqual(
            {
                row["bucket"]: row["in_timezone"]
                for row in preview["onboarding"]
            },
            {"first_week": 2, "more_fleets": 1},
        )


class StrategicTimezoneTests(TimezoneInviteTestBase):
    def test_strategic_fc_on_a_strategic_fleet_chooses_any_timezone(self):
        fleet = self.standard_fleet(
            type="strategic", created_by=self.strat, start_time=US_EVENING
        )
        body = self.call("get", f"/{fleet.id}/invites", self.strat).json()
        self.assertTrue(body["can_choose_timezones"])
        added = self.preview(
            fleet,
            self.strat,
            tribe_group_ids=[self.group.id],
            timezones=["USTZ", "EUTZ"],
        )
        self.assertEqual(added["other_timezones"], 0)
        anyone = self.preview(
            fleet,
            self.strat,
            tribe_group_ids=[self.group.id],
            timezones=["any"],
        )
        self.assertEqual(anyone["other_timezones"], 0)
        default = self.preview(
            fleet, self.strat, tribe_group_ids=[self.group.id]
        )
        self.assertEqual(default["other_timezones"], 1)

    def test_private_fleets_let_the_strategic_fc_choose(self):
        fleet = self.private_fleet(start_time=US_EVENING)
        preview = self.preview(
            fleet,
            self.strat,
            tribe_group_ids=[self.group.id],
            timezones=["any"],
        )
        self.assertEqual(preview["other_timezones"], 0)

    def test_strategic_fc_on_a_non_strategic_fleet_cannot_choose(self):
        fleet = self.standard_fleet(
            created_by=self.strat, start_time=US_EVENING
        )
        body = self.call("get", f"/{fleet.id}/invites", self.strat).json()
        self.assertFalse(body["can_choose_timezones"])


class CandidateTimezoneTests(TimezoneInviteTestBase):
    def test_pilots_carry_their_timezones(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        rows = self.call(
            "get", f"/{fleet.id}/invites/candidates?q=Tre", self.fc
        ).json()
        pilot = next(row for row in rows if row["kind"] == "pilot")
        self.assertEqual(
            pilot["timezone"], {"brackets": ["EUTZ"], "source": "activity"}
        )

    def test_corporations_count_members_in_timezone(self):
        fleet = self.standard_fleet(start_time=US_EVENING)
        corp = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Black Omega Security",
            ticker="OMEGA",
        )
        for user in (self.pilot, self.eu, self.unknown):
            EveCharacter.objects.filter(user=user).update(
                corporation_id=corp.corporation_id
            )
        rows = self.call(
            "get", f"/{fleet.id}/invites/candidates?q=Omega", self.fc
        ).json()
        row = next(row for row in rows if row["kind"] == "corporation")
        self.assertEqual((row["members"], row["in_timezone"]), (3, 2))
        rows = self.call(
            "get",
            f"/{fleet.id}/invites/candidates?q=Omega&timezones=EUTZ%2B",
            self.fc,
        ).json()
        row = next(row for row in rows if row["kind"] == "corporation")
        # EUTZ+ alone: only the pilot with no timezone yet.
        self.assertEqual(row["in_timezone"], 1)
