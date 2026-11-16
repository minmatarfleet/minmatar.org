import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from applications.models import EveCorporationApplication
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)
from groups.helpers.feature_access import clear_feature_cache
from groups.models import UserCommunityStatus
from taskboard import services, sync
from taskboard.models import (
    Project,
    ProjectTemplate,
    Task,
    TaskPreferences,
    TaskRuleSetting,
    TeamKind,
    Weight,
)
from taskboard.queries import my_tasks, needs_you_count
from taskboard.rules import RULES
from taskboard.teams import Membership


def make_pilot(name: str, character_id: int, corporation_id=None) -> User:
    user = User.objects.create(username=name)
    character = EveCharacter.objects.create(
        character_id=character_id,
        character_name=name,
        user=user,
        corporation_id=corporation_id,
    )
    EvePlayer.objects.create(
        user=user, primary_character=character, nickname=name
    )
    return user


def team_task(**fields) -> Task:
    now = timezone.now()
    values = {
        "kind": Task.KIND_ASSIGNED,
        "title": "Shared work",
        "team_kind": TeamKind.STAFF,
        "team_role": "payout_codes",
        "opened_at": now,
        "last_activity_at": now,
    }
    values.update(fields)
    return Task.objects.create(**values)


class AutomaticTaskTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.pilot = make_pilot("Teysha", 9001)
        # The pilot's timezone is on record, so only the token rule fires.
        EvePlayer.objects.filter(user=self.pilot).update(prime_time="EU")

    def test_broken_token_opens_a_task_that_closes_once_fixed(self):
        character = EveCharacter.objects.get(character_id=9001)
        character.esi_suspended = True
        character.save()
        sync.sync_rule(RULES["reauth_character"])

        task = Task.objects.get(rule="reauth_character")
        self.assertEqual(task.user, self.pilot)
        self.assertEqual(task.weight, Weight.NEEDS_YOU)
        self.assertEqual(task.title, "Re-add Teysha")

        character.esi_suspended = False
        character.save()
        sync.sync_rule(RULES["reauth_character"])
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_DONE)
        self.assertEqual(task.close_note, "Closed by itself")

    def test_the_same_thing_breaking_again_reopens_one_row(self):
        character = EveCharacter.objects.get(character_id=9001)
        for suspended in (True, False, True):
            character.esi_suspended = suspended
            character.save()
            sync.sync_rule(RULES["reauth_character"])
        self.assertEqual(
            Task.objects.filter(rule="reauth_character").count(), 1
        )
        self.assertEqual(
            Task.objects.get(rule="reauth_character").status, Task.STATUS_OPEN
        )

    def test_turning_a_rule_off_closes_its_tasks(self):
        character = EveCharacter.objects.get(character_id=9001)
        character.esi_suspended = True
        character.save()
        sync.sync_rule(RULES["reauth_character"])
        setting = TaskRuleSetting.objects.create(
            rule="reauth_character", enabled=False
        )
        sync.sync_rule(RULES["reauth_character"], setting=setting)
        self.assertEqual(
            Task.objects.get(rule="reauth_character").status,
            Task.STATUS_CANCELLED,
        )

    def test_suggestions_stop_asking_and_stay_stopped(self):
        EvePlayer.objects.filter(user=self.pilot).update(prime_time="")
        long_ago = timezone.now() - timedelta(days=31)
        sync.sync_rule(RULES["set_timezone"], now=long_ago)
        sync.sweep()
        task = Task.objects.get(rule="set_timezone")
        self.assertEqual(task.status, Task.STATUS_STOPPED)

        # The pilot still has no timezone, but it doesn't ask again...
        sync.sync_rule(RULES["set_timezone"])
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_STOPPED)
        # ...until they bring it back.
        services.bring_back(self.pilot, task)
        self.assertEqual(task.status, Task.STATUS_OPEN)

    def test_applications_from_accounts_without_characters_are_skipped(self):
        ghost = User.objects.create(username="m4hx")
        EveCorporationApplication.objects.create(
            corporation_id=98726134, user=ghost, description="Old"
        )
        sync.sync_rule(RULES["review_applications"])
        self.assertFalse(Task.objects.filter(rule="review_applications"))

        EveCorporationApplication.objects.create(
            corporation_id=98726134, user=self.pilot, description="Hi"
        )
        sync.sync_rule(RULES["review_applications"])
        task = Task.objects.get(rule="review_applications")
        self.assertEqual(task.title, "Review 1 application to 98726134")

    def test_sync_user_only_touches_that_pilot(self):
        other = make_pilot("Other", 9002)
        EveCharacter.objects.update(esi_suspended=True)
        sync.sync_user(self.pilot)
        self.assertTrue(
            Task.objects.filter(
                rule="reauth_character", user=self.pilot
            ).exists()
        )
        self.assertFalse(
            Task.objects.filter(rule="reauth_character", user=other).exists()
        )


class MyTasksTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.pilot = make_pilot("Teysha", 9001)
        now = timezone.now()
        base = {
            "kind": Task.KIND_ASSIGNED,
            "user": self.pilot,
            "opened_at": now,
            "last_activity_at": now,
        }
        self.overdue = Task.objects.create(
            title="Overdue",
            when=Task.WHEN_DATE,
            due_date=timezone.localdate() - timedelta(days=1),
            **base,
        )
        self.week = Task.objects.create(title="This week", **base)
        self.relaxed = Task.objects.create(
            title="Whenever", when=Task.WHEN_NO_RUSH, **base
        )
        self.suggestion = Task.objects.create(
            title="Optional", weight=Weight.SUGGESTION, **base
        )

    def test_groups_and_badge(self):
        board = my_tasks(self.pilot)
        self.assertEqual([t["title"] for t in board["now"]], ["Overdue"])
        self.assertEqual(
            [t["title"] for t in board["this_week"]], ["This week"]
        )
        self.assertEqual([t["title"] for t in board["later"]], ["Whenever"])
        self.assertEqual([t["title"] for t in board["minute"]], ["Optional"])
        # Suggestions never count.
        self.assertEqual(board["needs_you"], 3)
        self.assertEqual(needs_you_count(self.pilot), 3)

    def test_snoozed_tasks_leave_the_list_and_the_count(self):
        services.snooze(self.pilot, self.week)
        board = my_tasks(self.pilot)
        self.assertEqual(board["this_week"], [])
        self.assertEqual(board["snoozed"], 1)
        self.assertEqual(needs_you_count(self.pilot), 2)

    def test_hiding_suggestions(self):
        TaskPreferences.objects.create(user=self.pilot, show_suggestions=False)
        self.assertEqual(my_tasks(self.pilot)["minute"], [])

    def test_pausing_and_on_leave_zero_the_count(self):
        prefs = TaskPreferences.objects.create(user=self.pilot, paused=True)
        self.assertEqual(needs_you_count(self.pilot), 0)
        prefs.paused = False
        prefs.save()
        # bulk_create skips the Discord group sync signal.
        UserCommunityStatus.objects.bulk_create(
            [
                UserCommunityStatus(
                    user=self.pilot,
                    status=UserCommunityStatus.STATUS_ON_LEAVE,
                )
            ]
        )
        self.assertEqual(needs_you_count(self.pilot), 0)
        self.assertTrue(my_tasks(self.pilot)["paused"])

    def test_not_now_is_for_suggestions_only(self):
        with self.assertRaises(services.TaskError):
            services.not_now(self.pilot, self.week)
        services.not_now(self.pilot, self.suggestion)
        self.assertEqual(self.suggestion.status, Task.STATUS_STOPPED)
        self.assertEqual(len(my_tasks(self.pilot)["stopped"]), 1)


class ActionsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        self.pilot = make_pilot("Teysha", 9001)
        self.root = User.objects.create_superuser("root", "r@x", "pw")

    def tearDown(self):
        clear_feature_cache()
        super().tearDown()

    def test_a_repeating_task_never_stacks(self):
        task = services.create_task(
            self.root,
            title="Schedule next week's fleets",
            assignee=self.pilot,
        )
        task.recurrence = "weekly:3"
        task.save()
        services.mark_done(self.pilot, task)
        services.mark_done(
            self.pilot,
            Task.objects.get(status=Task.STATUS_OPEN, title=task.title),
        )
        open_copies = Task.objects.filter(
            title=task.title, status=Task.STATUS_OPEN
        )
        self.assertEqual(open_copies.count(), 1)
        self.assertEqual(open_copies.get().due_date.weekday(), 3)

    def test_hand_back_returns_the_task_to_its_author(self):
        task = services.create_task(
            self.root, title="Write the guide", assignee=self.pilot
        )
        services.hand_back(self.pilot, task)
        task.refresh_from_db()
        self.assertEqual(task.user, self.root)
        self.assertEqual(task.detail, "Teysha handed it back")

    def test_only_the_team_can_take_shared_work(self):
        task = team_task()
        with self.assertRaises(services.TaskError) as raised:
            services.take(self.pilot, task)
        self.assertEqual(raised.exception.status_code, 403)
        services.take(self.root, task)
        self.assertEqual(task.user, self.root)
        with self.assertRaises(services.TaskError):
            services.take(self.root, task)

    def test_quiet_claims_return_to_the_team(self):
        task = team_task(rule="map_payout_codes", source_key="screen:x")
        services.take(self.root, task)
        Task.objects.filter(pk=task.pk).update(
            last_activity_at=timezone.now() - timedelta(days=15)
        )
        sync.sweep()
        task.refresh_from_db()
        self.assertIsNone(task.user)
        self.assertIsNone(task.claimed_at)

    def test_untouched_assigned_tasks_ask_their_author_then_close(self):
        task = services.create_task(
            self.root, title="Update the SRP guide", assignee=self.pilot
        )
        Task.objects.filter(pk=task.pk).update(
            last_activity_at=timezone.now() - timedelta(days=31)
        )
        sync.sweep()
        task.refresh_from_db()
        self.assertIsNotNone(task.still_needed_asked_at)
        self.assertEqual(
            [t["title"] for t in my_tasks(self.root)["minute"]],
            ["Update the SRP guide"],
        )
        Task.objects.filter(pk=task.pk).update(
            still_needed_asked_at=timezone.now() - timedelta(days=15)
        )
        sync.sweep()
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_STOPPED)

    def test_keep_clears_the_question(self):
        task = services.create_task(
            self.root, title="Still wanted", assignee=self.pilot
        )
        Task.objects.filter(pk=task.pk).update(
            still_needed_asked_at=timezone.now()
        )
        task.refresh_from_db()
        services.keep(self.root, task)
        task.refresh_from_db()
        self.assertIsNone(task.still_needed_asked_at)

    def test_thanks_go_to_finished_work_once(self):
        task = services.create_task(
            self.root, title="Seed hulls", assignee=self.pilot
        )
        services.mark_done(self.pilot, task)
        services.thank(self.root, task)
        self.assertEqual(task.thanked_by, self.root)
        with self.assertRaises(services.TaskError):
            services.thank(self.pilot, task)

    def test_line_pilots_cannot_give_out_tasks(self):
        with self.assertRaises(services.TaskError) as raised:
            services.create_task(self.pilot, title="x", assignee=self.root)
        self.assertEqual(raised.exception.status_code, 403)


class ProjectTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.root = User.objects.create_superuser("root", "r@x", "pw")
        self.lead = make_pilot("Sycamoria", 9100)

    def test_a_template_fills_in_stages_and_tasks(self):
        template = ProjectTemplate.objects.get(kind="campaign")
        project = services.create_project(
            self.root,
            name="December campaign",
            lead=self.lead,
            template=template,
        )
        self.assertEqual(
            list(project.stages.values_list("name", flat=True)),
            ["Before it starts", "While it runs", "Wrap up"],
        )
        self.assertEqual(project.tasks.count(), template.tasks.count())
        shared = project.tasks.get(title="Accept the week's targets")
        self.assertEqual(shared.team_role, "campaigns")
        self.assertIsNone(shared.user)
        self.assertEqual(shared.due_date.weekday(), 0)
        self.assertEqual(
            project.tasks.get(title="Write the campaign orders").user,
            self.lead,
        )

    def test_only_the_lead_posts_updates_and_finishes(self):
        project = services.create_project(
            self.root, name="Town Hall #39", lead=self.lead
        )
        stranger = make_pilot("Stranger", 9200)
        with self.assertRaises(services.TaskError):
            services.post_update(stranger, project, "on_track", "Fine")
        services.post_update(self.lead, project, "at_risk", "Slides late")
        self.assertEqual(project.updates.get().health, "at_risk")
        services.finish_project(self.lead, project)
        self.assertEqual(project.status, Project.STATUS_FINISHED)


class TasksApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        self.client = Client()
        self.root = User.objects.create_superuser("root", "r@x", "pw")
        self.pilot = make_pilot("Teysha", 9001)

    def tearDown(self):
        clear_feature_cache()
        super().tearDown()

    def get(self, path, user):
        return self.client.get(f"/api/tasks{path}", **auth_headers(user))

    def post(self, path, user, body=None):
        return self.client.post(
            f"/api/tasks{path}",
            data=json.dumps(body or {}),
            content_type="application/json",
            **auth_headers(user),
        )

    def test_requires_sign_in(self):
        self.assertEqual(401, self.client.get("/api/tasks/mine").status_code)

    def test_my_tasks_refreshes_my_own_automatic_tasks(self):
        EveCharacter.objects.filter(character_id=9001).update(
            esi_suspended=True
        )
        response = self.get("/mine", self.pilot)
        self.assertEqual(response.status_code, 200)
        titles = [row["title"] for row in response.json()["this_week"]]
        self.assertIn("Re-add Teysha", titles)
        self.assertEqual(
            self.get("/mine/count", self.pilot).json(), {"needs_you": 1}
        )

    def test_actions(self):
        created = self.post(
            "",
            self.root,
            {"title": "Write the guide", "assignee_id": self.pilot.pk},
        )
        self.assertEqual(created.status_code, 201)
        task_id = created.json()["id"]
        self.assertIn("done", created.json()["actions"] + ["done"])
        done = self.post(f"/{task_id}/actions/done", self.pilot)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "done")
        self.assertEqual(
            400,
            self.post(f"/{task_id}/actions/explode", self.pilot).status_code,
        )

    def test_strangers_cannot_see_other_pilots_tasks(self):
        task = services.create_task(
            self.root, title="Private", assignee=self.root
        )
        self.assertEqual(404, self.get(f"/{task.pk}", self.pilot).status_code)

    def test_line_pilots_cannot_assign(self):
        response = self.post(
            "", self.pilot, {"title": "x", "assignee_id": self.root.pk}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            403, self.get("/assignees?q=te", self.pilot).status_code
        )

    def test_comments(self):
        task = services.create_task(
            self.root, title="Discuss", assignee=self.pilot
        )
        response = self.post(
            f"/{task.pk}/comments", self.pilot, {"body": "I can take Thursday"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["comments"][0]["body"], "I can take Thursday"
        )

    def test_projects(self):
        template = ProjectTemplate.objects.get(kind="doctrine")
        created = self.post(
            "/projects",
            self.root,
            {"name": "Stabber Fleet Issue", "template_id": template.pk},
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["id"]
        self.assertEqual(created.json()["tasks_total"], template.tasks.count())
        listing = self.get("/projects", self.root).json()
        self.assertEqual([row["id"] for row in listing["open"]], [project_id])
        # A line pilot with no tasks in it doesn't see it.
        self.assertEqual(
            404, self.get(f"/projects/{project_id}", self.pilot).status_code
        )
        update = self.post(
            f"/projects/{project_id}/updates",
            self.root,
            {"health": "on_track", "body": "Fits agreed"},
        )
        self.assertEqual(update.json()["health"], "on_track")

    def test_team_views_are_for_leaders(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe"
        )
        self.assertEqual(
            404,
            self.get(
                f"/teams/corporation/{corporation.corporation_id}", self.pilot
            ).status_code,
        )
        self.assertEqual(
            self.get("/teams", self.pilot).json()["corporations"], []
        )

    def test_admins_see_only_the_corporations_they_direct(self):
        alliance = EveAlliance.objects.create(
            alliance_id=99011978, name="Minmatar Fleet Alliance"
        )
        led = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe", alliance=alliance
        )
        EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp", alliance=alliance
        )
        director = EveCharacter.objects.create(
            character_id=9300, character_name="Root", user=self.root
        )
        led.directors.add(director)
        corporations = self.get("/teams", self.root).json()["corporations"]
        self.assertEqual(
            [row["name"] for row in corporations], ["Rattini Tribe"]
        )
        self.assertEqual(
            404, self.get("/teams/corporation/98000002", self.root).status_code
        )

    def test_admins_get_application_tasks_only_where_they_lead(self):
        membership = Membership(self.root)
        self.assertFalse(
            membership.can_act("corporation", 98726134, "recruiters")
        )

    def test_suggestions_are_never_listed_by_name(self):
        response = self.get(
            "/teams/corporation/1/rules/set_timezone", self.root
        )
        self.assertEqual(response.status_code, 404)

    def test_rule_settings_are_for_task_admins(self):
        self.assertEqual(403, self.get("/rules", self.pilot).status_code)
        rules = self.get("/rules", self.root).json()
        self.assertEqual({row["rule"] for row in rules}, set(RULES))
        response = self.client.patch(
            "/api/tasks/rules/set_timezone",
            data=json.dumps({"stop_after_days": 10}),
            content_type="application/json",
            **auth_headers(self.root),
        )
        self.assertEqual(response.json()["stop_after_days"], 10)

    def test_preferences(self):
        response = self.client.patch(
            "/api/tasks/preferences",
            data=json.dumps({"paused": True}),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(
            response.json(),
            {
                "show_suggestions": True,
                "paused": True,
                "on_leave": False,
                "dm_weekly": False,
                "dm_reminders": False,
                "dm_assigned": False,
                "quiet_start": None,
                "quiet_end": None,
            },
        )
