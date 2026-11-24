import json
from datetime import timedelta
from unittest.mock import patch

import factory
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from esi.models import Scope, Token

from app.test import TestCase
from app.testing import auth_headers
from discord.models import DiscordUser
from esi_health import services
from esi_health.models import EsiMessage, ScopeRollout
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.endpoints.characters._helpers import build_character_response
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)
from eveonline.scopes import (
    TokenType,
    BASIC_SCOPES,
    DIRECTOR_SCOPES,
    FACTION_WARFARE_SCOPES,
    INDUSTRY_SCOPES,
    NOT_GATED_SCOPES,
    scopes_for,
)
from groups.models import UserCommunityStatus
from notifications.models import NotificationDelivery
from taskboard import sync
from taskboard.models import Task, TeamKind, Weight
from taskboard.rules import RULES

CORP = 98726134
OTHER_CORP = 98647659
PROJECTS = "esi-corporations.read_projects.v1"
STRUCTURE_SEARCH = "esi-search.search_structures.v1"
UP_TO_DATE = set(scopes_for(TokenType.FACTION_WARFARE))


def token_with(character_id: int, scopes) -> Token:
    token = Token.objects.create(character_id=character_id)
    for name in scopes:
        token.scopes.add(Scope.objects.get_or_create(name=name)[0])
    return token


@factory.django.mute_signals(signals.pre_save, signals.post_save)
def character(character_id, name, user=None, corporation_id=CORP, **fields):
    return EveCharacter.objects.create(
        character_id=character_id,
        character_name=name,
        user=user,
        corporation_id=corporation_id,
        **fields,
    )


@factory.django.mute_signals(signals.pre_save, signals.post_save)
def corporation(corporation_id, name, ticker):
    alliance, _ = EveAlliance.objects.get_or_create(
        alliance_id=MINMATAR_FLEET_ALLIANCE_ID, defaults={"name": "FL33T"}
    )
    return EveCorporation.objects.create(
        corporation_id=corporation_id,
        name=name,
        ticker=ticker,
        alliance=alliance,
        member_count=10,
    )


def pilot(name, main_id, corporation_id=CORP, **fields):
    user = User.objects.create(username=name.lower())
    main = character(main_id, name, user, corporation_id, **fields)
    EvePlayer.objects.create(user=user, primary_character=main, nickname=name)
    return user, main


class NeedsReaddTestCase(TestCase):
    def setUp(self):
        super().setUp()
        corporation(CORP, "Rattini Tribe", "A-RAT")
        self.user, self.main = pilot(
            "Fariius", 1001, esi_suspended=True, esi_token_level="Basic"
        )

    def test_suspended_and_lost_tokens_need_readding(self):
        lost = character(1002, "Flee65", self.user, esi_token_level="Basic")
        never = character(1003, "Fresh", self.user)
        exempt = character(
            1004, "Parked", self.user, esi_suspended=True, exempt=True
        )
        broken = set(
            EveCharacter.objects.filter(services.needs_readd_q()).values_list(
                "character_id", flat=True
            )
        )
        self.assertEqual(broken, {1001, 1002})
        self.assertTrue(services.needs_readd(lost))
        self.assertFalse(services.needs_readd(never))
        self.assertFalse(services.needs_readd(exempt))

    def test_account_page_reads_a_lost_token_as_suspended(self):
        lost = character(1002, "Flee65", self.user, esi_token_level="Basic")
        lost.tag_count = 1
        item = build_character_response(lost, self.main)
        self.assertEqual(item.token_status, "SUSPENDED")
        self.assertIn("ESI_SUSPENDED", item.flags)

    def test_a_main_and_its_alts_are_two_tasks(self):
        for index, name in enumerate(("Flee65", "Detoxx", "Oneillies")):
            character(1010 + index, name, self.user, esi_token_level="Basic")
        sync.sync_rule(RULES["reauth_character"])
        titles = sorted(
            Task.objects.filter(rule="reauth_character").values_list(
                "title", flat=True
            )
        )
        self.assertEqual(titles, ["Re-add 3 alts", "Re-add Fariius"])
        alts = Task.objects.get(rule="reauth_character", source_key="alts")
        self.assertEqual(alts.detail, "Detoxx, Flee65, Oneillies")
        self.assertEqual(alts.link_url, "/account/?readd=alts")

    def test_fixing_the_main_closes_only_its_task(self):
        character(1010, "Flee65", self.user, esi_token_level="Basic")
        sync.sync_rule(RULES["reauth_character"])
        self.main.esi_suspended = False
        self.main.token = token_with(1001, BASIC_SCOPES)
        self.main.save()
        sync.sync_rule(RULES["reauth_character"])
        open_titles = list(
            Task.objects.filter(
                rule="reauth_character", status=Task.STATUS_OPEN
            ).values_list("title", flat=True)
        )
        self.assertEqual(open_titles, ["Re-add Flee65"])


class ScopeRolloutTestCase(TestCase):
    def setUp(self):
        super().setUp()
        corporation(CORP, "Rattini Tribe", "A-RAT")
        self.user, self.main = pilot(
            "Fariius",
            1001,
            esi_token_level="Basic",
            esi_scope_groups=["Basic", "FactionWarfare"],
            token=token_with(1001, UP_TO_DATE - {STRUCTURE_SEARCH}),
        )
        self.rollout = ScopeRollout.objects.get(scope=STRUCTURE_SEARCH)

    def _task(self):
        sync.sync_rule(RULES["update_scopes"])
        return Task.objects.filter(rule="update_scopes").first()

    def test_nobody_is_asked_until_a_superuser_asks(self):
        self.assertEqual(self.rollout.mode, ScopeRollout.MODE_NONE)
        sync.sync_rule(RULES["update_scopes"])
        self.assertFalse(Task.objects.filter(rule="update_scopes").exists())
        self.main.tag_count = 1
        self.assertNotIn(
            "SCOPES_OUTDATED",
            build_character_response(self.main, self.main).flags,
        )

    def test_suggest_opens_a_quiet_task_and_flags_the_character(self):
        self.rollout.mode = ScopeRollout.MODE_SUGGEST
        self.rollout.save()
        sync.sync_rule(RULES["update_scopes"])
        task = Task.objects.get(rule="update_scopes")
        self.assertEqual(task.weight, Weight.SUGGESTION)
        self.assertEqual(task.title, "Update ESI on Fariius")
        self.assertEqual(task.detail, "A newer login adds structure search")
        self.main.tag_count = 1
        self.assertIn(
            "SCOPES_OUTDATED",
            build_character_response(self.main, self.main).flags,
        )

    def test_a_scope_added_to_a_group_asks_without_a_rollout(self):
        # Clones were added to Basic with no ScopeRollout row.
        clones = "esi-clones.read_clones.v1"
        self.main.token = token_with(1001, UP_TO_DATE - {clones})
        self.main.save()
        task = self._task()
        self.assertEqual(task.title, "Update ESI on Fariius")
        self.assertEqual(task.detail, "A newer login adds newer Basic scopes")
        self.main.tag_count = 1
        self.assertIn(
            "SCOPES_OUTDATED",
            build_character_response(self.main, self.main).flags,
        )

    def test_a_group_the_character_has_is_checked_in_full(self):
        self.main.esi_scope_groups = ["Basic", "Industry", "FactionWarfare"]
        self.main.token = token_with(
            1001, UP_TO_DATE | set(INDUSTRY_SCOPES[1:])
        )
        self.main.save()
        self.assertEqual(
            self._task().detail, "A newer login adds newer Industry scopes"
        )

    def test_a_required_group_asks_characters_without_it(self):
        _, alt = pilot("Flee65", 1002, esi_token_level="Basic")
        alt.esi_scope_groups = ["Basic"]
        alt.token = token_with(1002, set(BASIC_SCOPES))
        alt.save()
        sync.sync_rule(RULES["update_scopes"])
        task = Task.objects.get(rule="update_scopes", user=alt.user)
        self.assertEqual(task.title, "Update ESI on Flee65")
        self.assertEqual(task.detail, "A newer login adds Faction Warfare")

    def test_up_to_date_guest_and_broken_tokens_are_not_asked(self):
        self.main.token = token_with(1001, UP_TO_DATE)
        self.main.save()
        user = User.objects.create(username="other")
        character(
            1003,
            "Guest",
            user,
            esi_token_level="Public",
            token=token_with(1003, ["publicData"]),
        )
        character(
            1004,
            "Broken",
            user,
            esi_token_level="Basic",
            esi_suspended=True,
            token=token_with(1004, []),
        )
        self.assertIsNone(self._task())

    def test_director_scopes_stay_a_corporation_task(self):
        self.main.esi_token_level = "Director"
        self.main.token = token_with(
            1001, UP_TO_DATE | (set(DIRECTOR_SCOPES) - {PROJECTS})
        )
        self.main.save()
        self.assertIsNone(self._task())

    def test_fixing_the_token_closes_the_task(self):
        self.main.token = token_with(1001, set(BASIC_SCOPES))
        self.main.esi_scope_groups = ["Basic"]
        self.main.save()
        self.assertEqual(self._task().status, Task.STATUS_OPEN)
        self.main.token = token_with(
            1001, set(BASIC_SCOPES) | set(FACTION_WARFARE_SCOPES)
        )
        self.main.save()
        self.assertEqual(self._task().status, Task.STATUS_DONE)

    def test_several_things_read_as_one_list(self):
        self.rollout.mode = ScopeRollout.MODE_SUGGEST
        self.rollout.save()
        self.main.esi_scope_groups = ["Basic", "Industry"]
        self.main.token = token_with(
            1001,
            set(BASIC_SCOPES) - {STRUCTURE_SEARCH, "esi-clones.read_clones.v1"}
            | set(INDUSTRY_SCOPES[1:]),
        )
        self.main.save()
        self.assertEqual(
            self._task().detail,
            "A newer login adds newer Basic scopes, structure search, "
            "newer Industry scopes and Faction Warfare",
        )


class DirectorTokenTestCase(TestCase):
    def setUp(self):
        super().setUp()
        corporation(CORP, "Rattini Tribe", "A-RAT")
        corporation(OTHER_CORP, "Soltech Armada", "SLTAR")
        corporation(98849119, "Wizards And Warlocks", "WZ.WL")
        self.ceo, ceo_main = pilot(
            "Sycamoria",
            2001,
            OTHER_CORP,
            esi_token_level="Director",
            token=token_with(2001, set(DIRECTOR_SCOPES) - {PROJECTS}),
        )
        EveCorporation.objects.filter(corporation_id=OTHER_CORP).update(
            ceo=ceo_main
        )
        pilot(
            "BearThatCares",
            2002,
            CORP,
            esi_token_level="Director",
            token=token_with(2002, DIRECTOR_SCOPES),
        )

    def test_states_follow_the_best_token(self):
        statuses = services.director_statuses([CORP, OTHER_CORP, 98849119])
        self.assertEqual(statuses[CORP].state, services.DIRECTOR_OK)
        self.assertEqual(statuses[OTHER_CORP].state, services.DIRECTOR_UPDATE)
        self.assertEqual(statuses[OTHER_CORP].missing_scopes, [PROJECTS])
        self.assertEqual(statuses[98849119].state, services.DIRECTOR_MISSING)

    def test_a_scope_nobody_requires_doesnt_count(self):
        ScopeRollout.objects.filter(scope=PROJECTS).update(
            mode=ScopeRollout.MODE_NONE
        )
        statuses = services.director_statuses([OTHER_CORP])
        self.assertEqual(statuses[OTHER_CORP].state, services.DIRECTOR_OK)

    def test_corporation_scopes_added_later_dont_count(self):
        # Director tokens granted before every corporation scope was added
        # keep their state: the new scopes are seeded "Don't ask".
        before = set(DIRECTOR_SCOPES) - NOT_GATED_SCOPES["Director"]
        EveCharacter.objects.filter(character_id=2002).update(
            token=token_with(2002, before)
        )
        statuses = services.director_statuses([CORP])
        self.assertEqual(statuses[CORP].state, services.DIRECTOR_OK)

    def test_corporation_tasks_for_leaders(self):
        sync.sync_rule(RULES["corp_director_token"])
        tasks = {
            task.team_id: task
            for task in Task.objects.filter(rule="corp_director_token")
        }
        self.assertEqual(set(tasks), {OTHER_CORP, 98849119})
        self.assertEqual(tasks[OTHER_CORP].team_kind, TeamKind.CORPORATION)
        self.assertEqual(tasks[OTHER_CORP].title, "Update the director token")
        self.assertEqual(
            tasks[OTHER_CORP].detail, "Corporation projects can't be read"
        )
        self.assertEqual(tasks[98849119].title, "Add a director token")

    def test_unlinked_characters_are_a_quiet_leader_task(self):
        character(3001, "Savron Nabaoth", None, CORP)
        character(3002, "Bush DaNasty", None, CORP)
        sync.sync_rule(RULES["corp_unlinked"])
        task = Task.objects.get(rule="corp_unlinked")
        self.assertEqual(task.team_id, CORP)
        self.assertEqual(task.weight, Weight.SUGGESTION)
        self.assertEqual(task.title, "Mail 2 characters with no account here")

    def test_leaders_see_their_director_token(self):
        response = Client().get(
            f"/api/esi-health/corporations/{OTHER_CORP}/director-token",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "update")
        self.assertEqual(body["missing_labels"], ["corporation projects"])
        self.assertTrue(body["holders"][0]["is_you"])

    def test_others_dont(self):
        stranger = User.objects.create(username="stranger")
        response = Client().get(
            f"/api/esi-health/corporations/{OTHER_CORP}/director-token",
            **auth_headers(stranger),
        )
        self.assertEqual(response.status_code, 403)


class ManageEsiHealthTestCase(TestCase):
    def setUp(self):
        super().setUp()
        corporation(CORP, "Rattini Tribe", "A-RAT")
        self.root = User.objects.create_superuser("root", "r@x", "pw")
        self.active, _ = pilot(
            "Fariius", 1001, esi_suspended=True, esi_token_level="Basic"
        )
        character(1002, "Flee65", self.active, esi_token_level="Basic")
        # bulk_create skips the Discord role sync signal.
        DiscordUser.objects.bulk_create(
            [DiscordUser(id=500001, discord_tag="flee65", user=self.active)]
        )
        self.away, _ = pilot(
            "Station", 1101, esi_suspended=True, esi_token_level="Basic"
        )
        # bulk_create skips the Discord group sync signal.
        UserCommunityStatus.objects.bulk_create(
            [
                UserCommunityStatus(
                    user=self.away, status=UserCommunityStatus.STATUS_ON_LEAVE
                )
            ]
        )
        self.client = Client()

    def get(self, path, user=None):
        return self.client.get(
            f"/api/esi-health/{path}", **auth_headers(user or self.root)
        )

    def test_only_superusers(self):
        self.assertEqual(self.get("pilots", self.active).status_code, 403)
        self.assertEqual(self.get("pilots").status_code, 200)

    def test_corporations_count_people_and_characters(self):
        rows = self.get("corporations").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["needs_readd"], 3)
        self.assertEqual(rows[0]["pilots_active"], 1)
        self.assertEqual(rows[0]["pilots_on_leave"], 1)
        self.assertEqual(rows[0]["director_state"], "missing")

    def test_pilots_put_the_main_first_and_on_leave_last(self):
        rows = self.get("pilots").json()
        self.assertEqual(
            [row["main_character_name"] for row in rows],
            ["Fariius", "Station"],
        )
        self.assertEqual(rows[0]["characters"], ["Fariius", "Flee65"])
        self.assertTrue(rows[1]["on_leave"])

    def test_scope_changes_list_and_change(self):
        rows = {row["scope"]: row for row in self.get("scopes").json()}
        self.assertEqual(rows[STRUCTURE_SEARCH]["mode"], "none")
        self.assertEqual(rows[PROJECTS]["unit"], "corporations")
        with patch("taskboard.tasks.sync_task_rule.delay") as delay:
            response = self.client.patch(
                f"/api/esi-health/scopes/{rows[STRUCTURE_SEARCH]['id']}",
                data=json.dumps({"mode": "suggest"}),
                content_type="application/json",
                **auth_headers(self.root),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "suggest")
        self.assertEqual(delay.call_count, 2)
        refused = self.client.patch(
            f"/api/esi-health/scopes/{rows[STRUCTURE_SEARCH]['id']}",
            data=json.dumps({"mode": "require"}),
            content_type="application/json",
            **auth_headers(self.root),
        )
        self.assertEqual(refused.status_code, 400)

    @patch("notifications.service._enqueue_delivery")
    def test_messages_skip_on_leave_and_repeat_sends(self, enqueue):
        def send():
            return self.client.post(
                "/api/esi-health/messages",
                data=json.dumps({"user_ids": []}),
                content_type="application/json",
                **auth_headers(self.root),
            ).json()

        with self.captureOnCommitCallbacks(execute=True):
            first = send()
        self.assertEqual(first["sent"], 1)
        self.assertEqual(enqueue.call_count, 1)
        self.assertEqual(first["on_leave"], 1)
        delivery = NotificationDelivery.objects.get(user=self.active)
        self.assertEqual(delivery.channel, "discord")
        self.assertIn("Fariius", delivery.payload["discord_message"])
        self.assertIn("1 other character", delivery.payload["discord_message"])

        second = send()
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["recently_messaged"], 1)

        EsiMessage.objects.update(sent_at=timezone.now() - timedelta(days=8))
        self.assertEqual(send()["sent"], 1)

    def test_pilots_without_discord_are_skipped(self):
        nobody, _ = pilot(
            "Quiet", 1201, esi_suspended=True, esi_token_level="Basic"
        )
        result = services.send_messages(self.root, [nobody.id])
        self.assertEqual(result.no_discord, [nobody.id])
        self.assertFalse(EsiMessage.objects.filter(user=nobody).exists())

    @patch("notifications.service._enqueue_delivery")
    def test_message_reaches_pilots_who_never_opted_in(self, enqueue):
        with self.captureOnCommitCallbacks(execute=True):
            services.send_messages(self.root, [self.active.id])
        self.assertTrue(enqueue.called)
        self.assertTrue(
            NotificationDelivery.objects.filter(user=self.active).exists()
        )
        self.assertFalse(
            NotificationDelivery.objects.filter(
                user=self.active, notification_type="tasks.reminder"
            ).exists()
        )
