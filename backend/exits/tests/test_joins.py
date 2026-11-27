import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.answers import answer
from exits.helpers.snapshots import record_members
from exits.models import Departure, FlaggedJoin, MemberSnapshot
from taskboard.rules import RULES


class FlaggedJoinTest(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.now = timezone.now()
        old_ceo = User.objects.create(username="old ceo")
        old_corp = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=EveCharacter.objects.create(
                character_id=2112000001,
                character_name="Arkan Veld",
                user=old_ceo,
            ),
        )
        self.pilot = User.objects.create(username="pilot")
        EveCharacter.objects.create(
            character_id=31, character_name="Dren Halvik", user=self.pilot
        )
        EveCharacter.objects.create(
            character_id=35, character_name="Dren Alt", user=self.pilot
        )
        departure = Departure.objects.create(
            corporation=old_corp,
            character_id=31,
            user=self.pilot,
            first_missing_at=self.now - timedelta(days=3),
            status="confirmed",
            confirmed_at=self.now,
            kind="exit",
        )
        answer(
            old_ceo,
            old_corp,
            [departure.pk],
            reason="kicked_other",
            can_rejoin=False,
            note="Awoxed",
        )

        self.ceo = User.objects.create(username="new ceo")
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000002,
            name="Other Corp",
            track_exits=True,
            ceo=EveCharacter.objects.create(
                character_id=2112000002,
                character_name="Sela Morn",
                user=self.ceo,
            ),
        )
        self.director = User.objects.create(username="director")
        director_character = EveCharacter.objects.create(
            character_id=2112000003,
            character_name="Director",
            user=self.director,
            corporation_id=98000002,
        )
        self.corporation.directors.add(director_character)
        self.member = User.objects.create(username="member")
        EveCharacter.objects.create(
            character_id=2112000004,
            character_name="Member",
            user=self.member,
            corporation_id=98000002,
        )
        MemberSnapshot.objects.create(
            corporation=self.corporation,
            member_ids=[1],
            alliance_id=None,
            taken_at=self.now - timedelta(hours=1),
        )

    def test_flagged_join_opens_task(self):
        # The alt joins: the flag covers the whole account.
        record_members(self.corporation, [1, 35], self.now)
        join = FlaggedJoin.objects.get()
        self.assertEqual(join.character_id, 35)
        self.assertEqual(join.user, self.pilot)
        self.assertEqual(join.outcome, "")
        [item] = RULES["exit_flagged_join"].collect(None)
        self.assertEqual(
            item.title,
            "Dren Alt joined Other Corp. They're marked can't rejoin",
        )
        self.assertIn("Example Corp", item.detail)
        self.assertIn("Awoxed", item.detail)
        self.assertEqual(item.team_role, "ceo")
        self.assertEqual(item.team_id, 98000002)

    def test_unflagged_join_opens_nothing(self):
        record_members(self.corporation, [1, 77], self.now)
        self.assertFalse(FlaggedJoin.objects.exists())
        self.assertEqual(RULES["exit_flagged_join"].collect(None), [])

    def test_keep_needs_note(self):
        record_members(self.corporation, [1, 35], self.now)
        join = FlaggedJoin.objects.get()
        url = f"/api/exits/flagged-joins/{join.pk}/keep"
        response = self.client.post(
            url,
            data=json.dumps({"note": " "}),
            content_type="application/json",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            url,
            data=json.dumps({"note": "Talked to him"}),
            content_type="application/json",
            **auth_headers(self.director),
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            url,
            data=json.dumps({"note": "Talked to him"}),
            content_type="application/json",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 200)
        join.refresh_from_db()
        self.assertEqual(join.outcome, "kept")
        self.assertEqual(join.resolved_by, self.ceo)
        self.assertEqual(RULES["exit_flagged_join"].collect(None), [])

    def test_removed_resolves_on_next_sync(self):
        record_members(self.corporation, [1, 35], self.now)
        join = FlaggedJoin.objects.get()
        response = self.client.post(
            f"/api/exits/flagged-joins/{join.pk}/remove",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 200)
        join.refresh_from_db()
        self.assertEqual(join.outcome, "")
        self.assertIsNotNone(join.removal_expected_at)
        record_members(self.corporation, [1], self.now + timedelta(hours=1))
        join.refresh_from_db()
        self.assertEqual(join.outcome, "removed")
        self.assertIsNotNone(join.resolved_at)

    def test_ceo_lists_open_joins(self):
        record_members(self.corporation, [1, 35], self.now)
        response = self.client.get(
            "/api/exits/corporations/98000002/flagged-joins",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 200)
        [row] = response.json()
        self.assertEqual(row["character_name"], "Dren Alt")
        self.assertEqual(row["flags"][0]["corporation_name"], "Example Corp")
        self.assertEqual(
            self.client.get(
                "/api/exits/corporations/98000002/flagged-joins",
                **auth_headers(self.director),
            ).status_code,
            403,
        )

    def test_history_tag_only_for_leadership(self):
        EveCharacter.objects.filter(character_id=35).update(
            corporation_id=98000002
        )
        url = "/api/eveonline/corporations/corporations/98000002/members"
        rows = self.client.get(url, **auth_headers(self.director)).json()
        flagged = {
            row["character_id"]: row["has_alliance_history"] for row in rows
        }
        self.assertTrue(flagged[35])
        self.assertFalse(flagged[2112000004])
        history = self.client.get(
            "/api/exits/corporations/98000002/members/35/history",
            **auth_headers(self.director),
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["corporation_name"], "Example Corp")
        self.assertEqual(
            self.client.get(
                "/api/exits/corporations/98000002/members/35/history",
                **auth_headers(self.member),
            ).status_code,
            403,
        )
