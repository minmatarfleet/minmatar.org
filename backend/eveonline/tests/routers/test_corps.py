from datetime import timedelta
from unittest.mock import patch

import factory
import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from django.core.cache import cache
from esi.models import Token

from app.test import TestCase
from applications.models import EveCorporationApplication
from discord.models import DiscordGuild
from eveonline.endpoints.corporations.get_corp_member_top import (
    sort_member_rows,
)
from eveonline.endpoints.corporations.schemas import CorporationMemberDetails
from eveonline.helpers.characters import (
    set_primary_character,
    update_character_with_affiliations,
)
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterSkill,
    EveCorporation,
    EveCorporationMedia,
    EvePlayer,
)
from groups.helpers import PEOPLE_TEAM
from groups.models import UserCommunityStatus

BASE_URL = "/api/eveonline/corporations/"


class CorporationRouterTestCase(TestCase):
    """Test cases for the corporation router."""

    def setUp(self):
        # Profile stats are cached per corporation id; start clean.
        cache.clear()
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.post_save.disconnect(
            sender=EveAlliance,
            dispatch_uid="eve_alliance_post_save",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def create_corp(self, corp_id: int, corp_name: str) -> EveCorporation:
        return EveCorporation.objects.create(
            corporation_id=corp_id,
            introduction="Intro",
            biography="Bio",
            executor_notes="Executor notes",
            timezones="TZ",
            requirements="Req",
            name=corp_name,
        )

    def test_get_corporations(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL + "corporations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(1, len(corps))
        self.assertEqual("TestCorp", corps[0]["corporation_name"])
        self.assertFalse(corps[0]["trial"])

        self.create_corp(23456, "TestCorp 2")

        response = self.client.get(
            BASE_URL + "corporations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(2, len(corps))

    def test_get_corporation(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL + "corporations/12345",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corp = response.json()
        self.assertEqual(12345, corp["corporation_id"])
        self.assertEqual("TestCorp", corp["corporation_name"])
        self.assertEqual("Executor notes", corp["executor_notes"])
        self.assertFalse(corp["trial"])

    def test_get_corporation_info(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL + "corporations/12345/info",
        )

        self.assertEqual(200, response.status_code)
        corp = response.json()
        self.assertEqual(12345, corp["corporation_id"])
        self.assertEqual("TestCorp", corp["corporation_name"])
        self.assertFalse(corp["trial"])
        self.assertNotIn("executor_notes", corp)
        self.assertEqual("Bio", corp["biography"])

    def test_corporation_trial_flag(self):
        corp = self.create_corp(12345, "TrialCorp")
        corp.trial = True
        corp.save()

        response = self.client.get(BASE_URL + "corporations")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()[0]["trial"])

        response = self.client.get(BASE_URL + "corporations/12345/info")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["trial"])

    def test_update_affiliations(self):
        EveCharacter.objects.create(
            character_id=100,
            character_name="Itsy Bitsy",
        )
        updated = update_character_with_affiliations(
            character_id=100, corporation_id=123, alliance_id=234
        )
        self.assertTrue(updated)
        character = EveCharacter.objects.get(character_id=100)
        self.assertEqual(character.corporation_id, 123)
        self.assertEqual(character.alliance_id, 234)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_corp_members(self):
        self.make_superuser()

        corp = self.create_corp(12345, "TestCorp")
        corp.ceo = EveCharacter.objects.create(
            character_id=10001,
            character_name="Boss Man",
            corporation_id=corp.corporation_id,
            user=self.user,
            token=Token.objects.create(
                character_id=10001,
                user=self.user,
            ),
        )
        corp.save()

        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        members = response.json()
        self.assertEqual(1, len(members))
        self.assertEqual("Boss Man", members[0]["character_name"])
        self.assertEqual(1, members[0]["token_count"])

    def test_public_info_hides_notes_and_lists_leadership(self):
        corp = self.create_corp(12345, "TestCorp")
        director = EveCharacter.objects.create(
            character_id=20002,
            character_name="Director Dan",
            user=self.user,
        )
        corp.directors.add(director)
        EvePlayer.objects.create(
            nickname="dan", user=self.user, prime_time="EU"
        )
        EveCorporationMedia.objects.create(
            corporation=corp,
            kind="youtube",
            url="https://youtu.be/abc123XYZ",
            caption="Op film",
        )

        response = self.client.get(BASE_URL + "corporations/12345/info")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertNotIn("executor_notes", payload)
        self.assertEqual("Op film", payload["media"][0]["caption"])
        self.assertEqual("abc123XYZ", payload["media"][0]["youtube_id"])
        self.assertEqual("director", payload["leadership"][0]["role"])
        self.assertEqual("EU", payload["leadership"][0]["prime_time"])

    def test_public_leadership_shows_mains_once(self):
        corp = self.create_corp(12345, "TestCorp")
        boss = User.objects.create(username="boss")
        boss_main = EveCharacter.objects.create(
            character_id=40001,
            character_name="Boss Main",
            user=boss,
        )
        boss_alt = EveCharacter.objects.create(
            character_id=40002,
            character_name="Boss Alt",
            user=boss,
        )
        set_primary_character(boss, boss_main)
        corp.ceo = boss_alt
        corp.save()

        director_user = User.objects.create(username="director-user")
        director_main = EveCharacter.objects.create(
            character_id=40003,
            character_name="Director Main",
            user=director_user,
        )
        director_alt = EveCharacter.objects.create(
            character_id=40004,
            character_name="Director Alt",
            user=director_user,
        )
        set_primary_character(director_user, director_main)
        corp.directors.add(director_main, director_alt)

        recruiter_user = User.objects.create(username="recruiter-user")
        recruiter_main = EveCharacter.objects.create(
            character_id=40005,
            character_name="Recruiter Main",
            user=recruiter_user,
        )
        recruiter_alt = EveCharacter.objects.create(
            character_id=40006,
            character_name="Recruiter Alt",
            user=recruiter_user,
        )
        set_primary_character(recruiter_user, recruiter_main)
        EvePlayer.objects.filter(user=recruiter_user).update(prime_time="EU")
        corp.recruiters.add(recruiter_alt)
        corp.recruiters.add(
            EveCharacter.objects.create(
                character_id=40007,
                character_name="Director Recruiter Alt",
                user=director_user,
            )
        )
        corp.directors.add(
            EveCharacter.objects.create(
                character_id=40008,
                character_name="Lone Wolf",
            )
        )

        token_user = User.objects.create(username="token-user")
        token_main = EveCharacter.objects.create(
            character_id=40009,
            character_name="Token Main",
            user=token_user,
        )
        set_primary_character(token_user, token_main)
        token_alt = EveCharacter.objects.create(
            character_id=40010,
            character_name="Token Alt",
            token=Token.objects.create(
                character_id=40010,
                user=token_user,
            ),
        )
        corp.directors.add(token_alt)

        gunner_user = User.objects.create(username="gunner-user")
        gunner_main = EveCharacter.objects.create(
            character_id=40011,
            character_name="Gunner Main",
            user=gunner_user,
        )
        gunner_alt = EveCharacter.objects.create(
            character_id=40012,
            character_name="Gunner Alt",
            user=gunner_user,
        )
        set_primary_character(gunner_user, gunner_main)
        corp.stewards.add(gunner_alt, director_alt)

        response = self.client.get(BASE_URL + "corporations/12345/info")
        self.assertEqual(200, response.status_code)
        leadership = response.json()["leadership"]
        by_role: dict[str, list] = {}
        for row in leadership:
            by_role.setdefault(row["role"], []).append(row)

        self.assertEqual(
            ["Boss Main"],
            [row["character_name"] for row in by_role["ceo"]],
        )
        self.assertEqual(40001, by_role["ceo"][0]["character_id"])

        director_names = {row["character_name"] for row in by_role["director"]}
        self.assertEqual(
            {"Director Main", "Lone Wolf", "Token Main"},
            director_names,
        )
        recruiter_rows = by_role["recruiter"]
        self.assertEqual(
            ["Recruiter Main"],
            [row["character_name"] for row in recruiter_rows],
        )
        self.assertEqual(40005, recruiter_rows[0]["character_id"])
        self.assertEqual("EU", recruiter_rows[0]["prime_time"])
        self.assertEqual(
            ["Gunner Main"],
            [row["character_name"] for row in by_role["steward"]],
        )
        self.assertEqual(40011, by_role["steward"][0]["character_id"])
        names = [row["character_name"] for row in leadership]
        self.assertEqual(len(names), len(set(names)))

    def test_public_info_counts_distinct_humans(self):
        corp = self.create_corp(12345, "TestCorp")
        corp.member_count = 10
        corp.save()
        EveCharacter.objects.create(
            character_id=30001,
            character_name="Pilot One",
            corporation_id=corp.corporation_id,
            user=self.user,
        )
        EveCharacter.objects.create(
            character_id=30002,
            character_name="Pilot Two",
            corporation_id=corp.corporation_id,
            user=self.user,
        )
        other = User.objects.create(username="other-pilot")
        EveCharacter.objects.create(
            character_id=30003,
            character_name="Pilot Three",
            corporation_id=corp.corporation_id,
            user=other,
        )
        EveCharacter.objects.create(
            character_id=30004,
            character_name="Unlinked",
            corporation_id=corp.corporation_id,
        )

        response = self.client.get(BASE_URL + "corporations/12345/info")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(10, payload["member_count"])
        self.assertEqual(2, payload["human_count"])
        self.assertNotIn("executor_notes", payload)

    def test_director_can_view_members_recruiter_cannot(self):
        corp = self.create_corp(12345, "TestCorp")
        director = EveCharacter.objects.create(
            character_id=20002,
            character_name="Director Dan",
            corporation_id=corp.corporation_id,
            user=self.user,
        )
        corp.directors.add(director)

        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Director Dan", response.json()[0]["character_name"])

        top = self.client.get(
            BASE_URL + "corporations/12345/members/top?metric=fleets",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, top.status_code)
        self.assertEqual("fleets", top.json()["metric"])
        self.assertEqual(
            "Director Dan", top.json()["members"][0]["character_name"]
        )

        corp.directors.clear()
        corp.recruiters.add(director)
        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()[0]["characters_hidden"])

        corp.recruiters.clear()
        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(403, response.status_code)

    def _roster_with_alts(self):
        """A People-team viewer and a member with a primary and two alts."""
        corp = self.create_corp(12345, "TestCorp")
        # People-team membership without firing the Discord group sync.
        patcher = patch(
            "eveonline.helpers.corporations.permissions.user_in_team",
            side_effect=lambda user, team: team == PEOPLE_TEAM,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        owner = User.objects.create_user(username="alt-owner")
        main = EveCharacter.objects.create(
            character_id=30001,
            character_name="Visible Main",
            corporation_id=corp.corporation_id,
            user=owner,
        )
        for character_id, name in ((30002, "Secret Alt"), (30003, "Hush Alt")):
            EveCharacter.objects.create(
                character_id=character_id,
                character_name=name,
                corporation_id=corp.corporation_id,
                user=owner,
            )
        EvePlayer.objects.create(
            nickname="owner", user=owner, primary_character=main
        )
        return corp

    def test_people_team_sees_counts_not_characters(self):
        self._roster_with_alts()
        for path in ("members", "members/top?metric=fleets"):
            response = self.client.get(
                BASE_URL + f"corporations/12345/{path}",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            self.assertEqual(200, response.status_code)
            body = response.content.decode()
            self.assertNotIn("Secret Alt", body)
            self.assertNotIn("30002", body)
            self.assertNotIn("Hush Alt", body)
            rows = response.json()
            rows = rows["members"] if isinstance(rows, dict) else rows
            self.assertEqual(1, len(rows))
            self.assertEqual("Visible Main", rows[0]["character_name"])
            self.assertTrue(rows[0]["characters_hidden"])
            self.assertEqual(2, rows[0]["hidden_character_count"])

        access = self.client.get(
            BASE_URL + "corporations/12345/members/access",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(
            {"can_view_members": True, "can_view_characters": False}, access
        )

    def test_superuser_sees_every_character(self):
        self._roster_with_alts()
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        names = {row["character_name"] for row in response.json()}
        self.assertEqual({"Visible Main", "Secret Alt", "Hush Alt"}, names)

    def test_members_include_primary_character(self):
        corp = self.create_corp(12345, "TestCorp")
        primary = EveCharacter.objects.create(
            character_id=20002,
            character_name="Director Dan",
            corporation_id=corp.corporation_id,
            user=self.user,
        )
        EveCharacter.objects.create(
            character_id=20003,
            character_name="Alt Ace",
            corporation_id=corp.corporation_id,
            user=self.user,
        )
        corp.directors.add(primary)
        EvePlayer.objects.create(
            nickname="dan",
            user=self.user,
            primary_character=primary,
        )
        # bulk_create skips the community group sync signal.
        UserCommunityStatus.objects.bulk_create(
            [UserCommunityStatus(user=self.user, status="trial")]
        )

        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        by_name = {row["character_name"]: row for row in response.json()}
        self.assertEqual("trial", by_name["Alt Ace"]["community_status"])
        self.assertEqual(
            primary.character_id,
            by_name["Director Dan"]["primary_character_id"],
        )
        self.assertEqual(
            "Director Dan",
            by_name["Director Dan"]["primary_character_name"],
        )
        self.assertEqual(
            primary.character_id,
            by_name["Alt Ace"]["primary_character_id"],
        )
        self.assertEqual(
            "Director Dan",
            by_name["Alt Ace"]["primary_character_name"],
        )

    def test_member_timezone_sort_uses_observed_buckets(self):
        us_active = CorporationMemberDetails(
            character_id=1,
            character_name="Zed",
            prime_time="EU",
            observed_prime_times=["US"],
        )
        eu_active = CorporationMemberDetails(
            character_id=2,
            character_name="Ann",
            prime_time="US",
            observed_prime_times=["EU"],
        )
        unset = CorporationMemberDetails(
            character_id=3,
            character_name="Mia",
            prime_time="US",
            observed_prime_times=[],
        )
        ordered = sort_member_rows(
            [us_active, unset, eu_active],
            "timezone",
        )
        self.assertEqual(
            ["Zed", "Ann", "Mia"],
            [row.character_name for row in ordered],
        )

    def test_admin_reports_missing_timezone_and_bot(self):
        corp = self.create_corp(12345, "TestCorp")
        director = EveCharacter.objects.create(
            character_id=20002,
            character_name="Director Dan",
            user=self.user,
        )
        corp.directors.add(director)
        corp.discord_guild = DiscordGuild.objects.create(
            guild_id=42, name="Corp Ops", is_active=True
        )
        corp.discord_invite_url = "https://discord.gg/example"
        corp.save()

        response = self.client.get(
            BASE_URL + "corporations/12345/admin",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["discord_bot_present"])
        self.assertEqual("Corp Ops", payload["discord_guild_name"])
        self.assertEqual(
            "Director Dan",
            payload["leadership_missing_prime_time"][0]["character_name"],
        )
        self.assertEqual("Executor notes", payload["executor_notes"])

    def test_managed_includes_director(self):
        corp = self.create_corp(12345, "TestCorp")
        director = EveCharacter.objects.create(
            character_id=20002,
            character_name="Director Dan",
            user=self.user,
        )
        corp.directors.add(director)
        response = self.client.get(
            BASE_URL + "managed",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertIn(12345, response.json())

    def test_application_process_stats_and_reviewer_queue(self):
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        corp = self.create_corp(12345, "TestCorp")
        now = timezone.now()
        accepted = EveCorporationApplication.objects.create(
            corporation_id=corp.corporation_id,
            user=self.user,
            description="Accepted",
            status="accepted",
        )
        EveCorporationApplication.objects.filter(pk=accepted.pk).update(
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=6),
        )
        applicant = User.objects.create(username="applicant")
        main = EveCharacter.objects.create(
            character_id=51001,
            character_name="Applicant Main",
            user=applicant,
        )
        set_primary_character(applicant, main)
        EveCharacterSkill.objects.create(
            skill_id=1,
            skill_name="Gunnery",
            skill_points=20_000_000,
            skill_level=5,
            character=main,
        )
        EveCorporationApplication.objects.create(
            corporation_id=corp.corporation_id,
            user=applicant,
            description="Please",
            status="pending",
        )

        info = self.client.get(BASE_URL + "corporations/12345/info")
        self.assertEqual(200, info.status_code)
        process = info.json()["application_process"]
        self.assertEqual(1, process["outstanding"])
        self.assertEqual(4.0, process["acceptance_days"])
        self.assertEqual(20_000_000, process["average_skill_points"])
        self.assertIsNotNone(process["applications_per_month"])
        self.assertNotIn("Applicant Main", info.content.decode())

        stranger = User.objects.create(username="stranger")
        stranger_token = jwt.encode(
            {"user_id": stranger.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        denied = self.client.get(
            BASE_URL + "corporations/12345/applications/open",
            HTTP_AUTHORIZATION=f"Bearer {stranger_token}",
        )
        self.assertEqual(403, denied.status_code)

        recruiter = EveCharacter.objects.create(
            character_id=51002,
            character_name="Recruiter",
            user=self.user,
        )
        corp.recruiters.add(recruiter)
        opened = self.client.get(
            BASE_URL + "corporations/12345/applications/open",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, opened.status_code)
        self.assertEqual("Applicant Main", opened.json()[0]["character_name"])
