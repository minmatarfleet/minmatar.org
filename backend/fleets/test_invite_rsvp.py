"""Signing up for a fleet invite from the one-time link
(docs/fleets/invite-rsvp.md)."""

from unittest.mock import patch

from django.core import signing
from django.test import Client

from capabilities.models import (
    CharacterAccount,
    CharacterAccountMember,
    CharacterFittingReadiness,
    FittingRequirementSet,
)
from eveonline.models import EveCharacter
from fittings.models import EveFitting
from fleets.helpers.invite_rsvp import SALT, mint_token
from fleets.helpers.private_fleet_discord import (
    answered_payload,
    invite_payload,
)
from fleets.helpers.private_fleets import target_progress
from fleets.models import (
    EveFleetFitting,
    EveFleetInvite,
    EveFleetShipTarget,
    EveFleetShipVolunteer,
)
from fleets.test_private_fleets import (  # pylint: disable=unused-import
    BASE_URL,
    PrivateFleetTestBase,
    setUpModule,
    tearDownModule,
)
from tribes.tests.publishing_fixtures import make_user


class RsvpTestBase(PrivateFleetTestBase):
    def setUp(self):
        super().setUp()
        self.fleet = self.private_fleet(invite_only=False)
        self.revelation = self._fit("RSVP Revelation", 19720)
        self.guardian = self._fit("RSVP Guardian", 11987)
        (self.invite_row,) = self.invite(self.fleet, self.pilot)
        self.main = EveCharacter.objects.get(user=self.pilot)
        self.alt = EveCharacter.objects.create(
            character_id=self.main.character_id + 7001,
            character_name="Teysha Alt",
            user=self.pilot,
        )
        self.no_skills = EveCharacter.objects.create(
            character_id=self.main.character_id + 7002,
            character_name="Teysha Farm",
            user=self.pilot,
        )
        self._ready(self.main, self.revelation)
        self._ready(self.main, self.guardian)
        self._ready(self.alt, self.guardian)

    def _fit(self, name, ship_id):
        fitting = EveFitting.objects.create(
            name=name, ship_id=ship_id, eft_format=f"[{name}, {name}]"
        )
        EveFleetFitting.objects.create(
            eve_fleet=self.fleet, fitting=fitting, name=name, ship_id=ship_id
        )
        return fitting

    def _ready(self, character, fitting):
        requirement_set, _ = FittingRequirementSet.objects.get_or_create(
            fitting=fitting,
            defaults={
                "sde_build": 1,
                "rules_version": 1,
                "input_key": "x",
                "capability": "dps",
            },
        )
        CharacterFittingReadiness.objects.create(
            character=character,
            fitting=fitting,
            requirement_set=requirement_set,
            hard_ready=True,
            doctrine_ready=True,
        )

    def anon(self, method, path, data=None):
        kwargs = {}
        if data is not None:
            kwargs = {"data": data, "content_type": "application/json"}
        return getattr(Client(), method)(f"{BASE_URL}{path}", **kwargs)

    def rsvp_token(self):
        return mint_token(self.invite_row)


class SignUpLinkTests(RsvpTestBase):
    def test_bot_gets_a_link_for_the_invited_pilot(self):
        bot = make_user("bot", perms=("view_evefleet",))
        with patch(
            "fleets.endpoints.private.answers.is_service_account",
            return_value=True,
        ):
            response = self.call(
                "post",
                f"/invites/{self.invite_row.id}/discord-available",
                bot,
                {"discord_user_id": 9001},
            )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIn("/fleets/rsvp/", body["url"])
        self.assertEqual(body["expires_minutes"], 10)

    def test_someone_else_pressing_gets_nothing(self):
        response = self.call(
            "post",
            f"/invites/{self.invite_row.id}/discord-available",
            self.outsider,
            {"discord_user_id": 9002},
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_dm_has_bot_buttons_and_no_character_names(self):
        payload = invite_payload(self.invite_row)
        labels = [b["label"] for b in payload["components"][0]["components"]]
        self.assertEqual(
            labels,
            ["I'm available", "I'm not available", "Stop fleet invites"],
        )
        self.assertTrue(
            all("url" not in b for b in payload["components"][0]["components"])
        )
        fields = [f["name"] for f in payload["embeds"][0]["fields"]]
        self.assertNotIn("Your characters", fields)
        self.assertIn(
            "Either answer is fine", payload["embeds"][0]["description"]
        )


class FormTests(RsvpTestBase):
    def test_lists_only_characters_that_can_fly_with_their_fits(self):
        response = self.anon("get", f"/rsvp/{self.rsvp_token()}")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        names = {c["name"]: c for c in body["characters"]}
        self.assertEqual(set(names), {"Teysha", "Teysha Alt"})
        self.assertEqual(body["hidden_count"], 1)
        self.assertEqual(
            {f["name"] for f in names["Teysha Alt"]["fits"]}, {"RSVP Guardian"}
        )
        self.assertEqual(sum(c["picked"] for c in body["characters"]), 1)
        self.assertEqual(body["fleet"]["fc_name"], "Casper")
        self.assertFalse(body["any_ship"])
        self.assertTrue(body["submit_token"])

    def test_accounts_are_reported(self):
        account = CharacterAccount.objects.create(user=self.pilot, number=1)
        for character in (self.main, self.alt):
            CharacterAccountMember.objects.create(
                character=character, account=account
            )
        body = self.anon("get", f"/rsvp/{self.rsvp_token()}").json()
        self.assertEqual({c["account"] for c in body["characters"]}, {1})

    def test_bad_or_expired_links_say_expired_and_nothing_else(self):
        response = self.anon("get", "/rsvp/not-a-token")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["detail"], "This link has expired.")
        with patch("django.core.signing.time.time", return_value=0):
            old = signing.dumps(
                {"i": self.invite_row.id, "u": self.pilot.id},
                salt=SALT,
                compress=True,
            )
        self.assertEqual(self.anon("get", f"/rsvp/{old}").status_code, 410)

    def test_token_for_someone_elses_invite_is_rejected(self):
        forged = signing.dumps(
            {"i": self.invite_row.id, "u": self.outsider.id},
            salt=SALT,
            compress=True,
        )
        self.assertEqual(self.anon("get", f"/rsvp/{forged}").status_code, 410)

    def test_started_fleet(self):
        self.fleet.status = "active"
        self.fleet.save()
        self.assertEqual(
            self.anon("get", f"/rsvp/{self.rsvp_token()}").status_code, 410
        )


class SubmitTests(RsvpTestBase):
    def submit(self, picks, confidence="high"):
        token = self.anon("get", f"/rsvp/{self.rsvp_token()}").json()[
            "submit_token"
        ]
        return self.anon(
            "post",
            f"/rsvp/{token}",
            {"picks": picks, "confidence": confidence},
        )

    def test_sign_up_with_two_characters(self):
        response = self.submit(
            [
                {
                    "character_id": self.main.character_id,
                    "fitting_id": self.revelation.id,
                },
                {
                    "character_id": self.alt.character_id,
                    "fitting_id": self.guardian.id,
                },
            ],
            "medium",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["answer"], "in")
        self.assertEqual(body["confidence"], "medium")
        self.assertEqual(len(body["ships"]), 2)
        self.invite_row.refresh_from_db()
        self.assertEqual(self.invite_row.confidence, "medium")
        payload = answered_payload(self.invite_row)
        self.assertIn(
            "10–15 minutes late", payload["embeds"][0]["description"]
        )

    def test_unticking_a_character_takes_their_ship_off(self):
        self.submit(
            [
                {
                    "character_id": self.alt.character_id,
                    "fitting_id": self.guardian.id,
                }
            ]
        )
        self.submit(
            [
                {
                    "character_id": self.main.character_id,
                    "fitting_id": self.guardian.id,
                }
            ]
        )
        self.assertEqual(
            list(
                EveFleetShipVolunteer.objects.filter(
                    eve_fleet=self.fleet
                ).values_list("character_id", flat=True)
            ),
            [self.main.character_id],
        )

    def test_character_that_cannot_fly_is_refused(self):
        response = self.submit(
            [
                {
                    "character_id": self.no_skills.character_id,
                    "fitting_id": self.guardian.id,
                }
            ]
        )
        self.assertEqual(response.status_code, 400)

    def test_low_confidence_is_not_counted(self):
        EveFleetShipTarget.objects.create(
            eve_fleet=self.fleet, name="Logi", target=2, ship_type_ids=[11987]
        )
        self.submit(
            [
                {
                    "character_id": self.alt.character_id,
                    "fitting_id": self.guardian.id,
                }
            ],
            "low",
        )
        self.assertEqual(target_progress(self.fleet)[0]["have"], 0)
        self.invite_row.refresh_from_db()
        self.invite_row.confidence = "high"
        self.invite_row.save()
        self.assertEqual(target_progress(self.fleet)[0]["have"], 1)

    def test_not_available(self):
        token = self.anon("get", f"/rsvp/{self.rsvp_token()}").json()[
            "submit_token"
        ]
        response = self.anon("post", f"/rsvp/{token}/not-available")
        self.assertEqual(response.status_code, 200, response.content)
        self.invite_row.refresh_from_db()
        self.assertEqual(self.invite_row.answer, EveFleetInvite.ANSWER_OUT)
        embed = answered_payload(self.invite_row)["embeds"][0]
        self.assertEqual(embed["title"], "You're not available for this one")
        self.assertIn(
            "at most one of these invites a week", embed["description"]
        )
