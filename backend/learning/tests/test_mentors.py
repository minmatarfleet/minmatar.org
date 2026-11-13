"""Mentor classes: matching, requests, hand-offs, reminders and close-out."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.utils import timezone

from app.testing import auth_headers
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EvePlayer
from learning.mentors import availability as avail
from learning.mentors import requirements as reqs
from learning.mentors import service
from learning.models import (
    ContentKind,
    MentorClass,
    MentorClassTeacher,
    MentorProfile,
    MentorRequest,
    UserLearningProgress,
)

BASE = "/api/learning/mentors"
US_EVENINGS = avail.Availability.build(["USTZ"], ["USTZ"], avail.ALL_DAYS)


def _user(name, character_id, discord_id):
    user = User.objects.create_user(username=name, password="x")
    character = EveCharacter.objects.create(
        character_id=character_id, character_name=name.title(), user=user
    )
    EvePlayer.objects.create(
        user=user, nickname=name, primary_character=character
    )
    DiscordUser.objects.create(
        id=discord_id, user=user, discord_tag=f"{name}#0"
    )
    return user


def _mentor(user, brackets=("USTZ",), days=avail.ALL_DAYS):
    return MentorProfile.objects.create(
        user=user,
        status=MentorProfile.STATUS_APPROVED,
        weekday_brackets=list(brackets),
        weekend_brackets=list(brackets),
        days=list(days),
    )


class AvailabilityTestCase(TestCase):
    def test_us_evening_on_an_eu_clock_counts_as_the_us_evening_day(self):
        # Saturday 01:00 UTC is Friday 20:00 in New York (November).
        moment = datetime(2026, 11, 14, 1, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(4, avail.evening_weekday("USTZ", moment))
        self.assertIsNone(avail.evening_weekday("EUTZ", moment))

    def test_weekday_and_weekend_brackets_are_separate(self):
        person = avail.Availability.build(["EUTZ"], ["AUTZ"], avail.ALL_DAYS)
        tuesday_eu = datetime(2026, 11, 10, 19, 0, tzinfo=dt_timezone.utc)
        saturday_eu = datetime(2026, 11, 14, 19, 0, tzinfo=dt_timezone.utc)
        self.assertTrue(avail.is_available(person, tuesday_eu))
        self.assertFalse(avail.is_available(person, saturday_eu))

    def test_suggested_slots_start_each_shared_evening(self):
        now = datetime(2026, 11, 12, 12, 0, tzinfo=dt_timezone.utc)
        slots = avail.suggested_slots(US_EVENINGS, US_EVENINGS, now)
        self.assertEqual(3, len(slots))
        self.assertTrue(all(slot.hour == 23 for slot in slots))
        self.assertTrue(slots[0] >= now + timedelta(hours=12))

    def test_fit(self):
        eu = avail.Availability.build(["EUTZ"], ["EUTZ"], avail.ALL_DAYS)
        self.assertEqual("evenings", avail.fit(US_EVENINGS, US_EVENINGS))
        self.assertEqual("none", avail.fit(US_EVENINGS, eu))


class RequirementsTestCase(TestCase):
    def setUp(self):
        self.pilot = _user("talisker", 2124705658, 11)

    def test_clean_rejects_unknown_kinds_and_bad_numbers(self):
        with self.assertRaises(reqs.RequirementError):
            reqs.clean([{"kind": "skills", "value": "x"}])
        with self.assertRaises(reqs.RequirementError):
            reqs.clean([{"kind": "accounts", "value": "two"}])
        self.assertEqual(
            [{"kind": "ready_fit", "value": ""}],
            reqs.clean([{"kind": "ready_fit", "value": "anything"}]),
        )

    def test_accounts_counts_characters_on_no_account(self):
        checks = reqs.check(self.pilot, [{"kind": "accounts", "value": "2"}])
        self.assertFalse(checks[0].met)
        self.assertEqual("You have 1", checks[0].detail)


@mock.patch("learning.mentors.service.queue_dm")
class RequestFlowTestCase(TestCase):
    def setUp(self):
        self.pilot = _user("talisker", 2124705658, 11)
        self.orion = _user("orion", 93672441, 22)
        self.syca = _user("sycamoria", 2116242012, 33)
        self.orion_profile = _mentor(self.orion)
        self.syca_profile = _mentor(self.syca)
        self.mc = MentorClass.objects.create(
            slug="small-gang",
            title="Small gang",
            status=MentorClass.STATUS_PUBLISHED,
            author=self.orion,
        )
        service.sync_learning(self.mc)
        for profile in (self.orion_profile, self.syca_profile):
            MentorClassTeacher.objects.create(
                mentor_class=self.mc, mentor=profile
            )

    def _ask(self, mentor=None):
        with self.captureOnCommitCallbacks(execute=True):
            return service.create_request(
                self.pilot,
                mentor or self.orion_profile,
                self.mc,
                note="Keep losing my Rifter",
                weekday_brackets=["USTZ"],
                weekend_brackets=["USTZ"],
                days=list(avail.ALL_DAYS),
            )

    def test_publishing_creates_the_learning(self, dm):
        self.mc.refresh_from_db()
        self.assertEqual(
            ContentKind.MENTOR_CLASS, self.mc.learning.content_kind
        )
        self.assertTrue(self.mc.learning.published)

    def test_request_dms_the_mentor(self, dm):
        req = self._ask()
        self.assertEqual(MentorRequest.STATUS_ASKED, req.status)
        self.assertEqual(22, dm.call_args.args[0])
        components = dm.call_args.kwargs["payload"]["components"][0]
        self.assertEqual(
            f"mentor:pass:{req.pk}", components["components"][1]["custom_id"]
        )

    def test_no_second_open_request_for_the_same_class(self, dm):
        self._ask()
        with self.assertRaises(service.MentorError):
            self._ask(self.syca_profile)

    def test_pass_hands_off_to_the_next_mentor_who_fits(self, dm):
        req = self._ask()
        new = service.pass_request(req, self.orion)
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_PASSED, req.status)
        self.assertEqual(self.syca_profile, new.mentor)
        self.assertEqual(req, new.passed_from)

    def test_no_mentor_left_expires_and_tells_the_pilot(self, dm):
        req = self._ask()
        new = service.pass_request(req, self.orion)
        self.assertIsNone(service.pass_request(new, self.syca))
        new.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_EXPIRED, new.status)

    def test_unanswered_for_two_days_moves_on(self, dm):
        req = self._ask()
        MentorRequest.objects.filter(pk=req.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        self.assertEqual(1, service.expire_unanswered())
        self.assertTrue(
            MentorRequest.objects.filter(
                passed_from=req, mentor=self.syca_profile
            ).exists()
        )

    def test_accept_books_and_dms_both_with_the_other_name(self, dm):
        req = self._ask()
        dm.reset_mock()
        starts = timezone.now() + timedelta(days=2)
        with self.captureOnCommitCallbacks(execute=True):
            service.accept(req, self.orion, starts, "A Rifter")
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_BOOKED, req.status)
        sent = {
            call.args[0]: call.kwargs["payload"] for call in dm.call_args_list
        }
        self.assertIn("@orion", sent[11]["content"])
        self.assertIn("@talisker", sent[22]["content"])

    def test_reminder_then_follow_up_then_done_completes_the_learning(
        self, dm
    ):
        req = self._ask()
        service.accept(req, self.orion, timezone.now() + timedelta(hours=5))
        dm.reset_mock()
        self.assertEqual(1, service.send_reminders())
        self.assertEqual(0, service.send_reminders())
        self.assertEqual(2, dm.call_count)
        MentorRequest.objects.filter(pk=req.pk).update(
            starts_at=timezone.now() - timedelta(days=3)
        )
        dm.reset_mock()
        self.assertEqual(1, service.send_follow_ups())
        self.assertEqual(2, dm.call_count)
        req.refresh_from_db()
        service.feedback(req, self.pilot, "bit", "Ran out of time")
        service.feedback(req, self.orion, "done", "Keen")
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_DONE, req.status)
        self.assertEqual("Ran out of time", req.pilot_note)
        self.assertTrue(
            UserLearningProgress.objects.filter(
                user=self.pilot, learning=self.mc.learning
            ).exists()
        )

    def test_moved_returns_the_request_to_the_mentor(self, dm):
        req = self._ask()
        service.accept(req, self.orion, timezone.now() + timedelta(hours=5))
        MentorRequest.objects.filter(pk=req.pk).update(
            starts_at=timezone.now() - timedelta(hours=1)
        )
        req.refresh_from_db()
        service.feedback(req, self.orion, "moved")
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_ASKED, req.status)
        self.assertIsNone(req.starts_at)

    def test_unanswered_follow_up_closes_unconfirmed(self, dm):
        req = self._ask()
        service.accept(req, self.orion, timezone.now() + timedelta(hours=5))
        MentorRequest.objects.filter(pk=req.pk).update(
            followed_up_at=timezone.now() - timedelta(days=8)
        )
        self.assertEqual(1, service.close_unconfirmed())

    def test_only_the_two_pilots_can_cancel(self, dm):
        req = self._ask()
        with self.assertRaises(service.MentorError):
            service.cancel(req, self.syca)
        service.cancel(req, self.pilot)
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_CANCELLED, req.status)

    def test_full_mentor_cannot_be_asked(self, dm):
        self.orion_profile.classes_per_week = 1
        self.orion_profile.save()
        other = _user("mccee", 91691792, 44)
        MentorRequest.objects.create(
            pilot=other,
            mentor=self.orion_profile,
            mentor_class=self.mc,
            status=MentorRequest.STATUS_BOOKED,
            starts_at=service.week_start() + timedelta(days=1),
        )
        with self.assertRaises(service.MentorError):
            self._ask()


@mock.patch("learning.mentors.service.queue_dm")
@mock.patch("learning.mentors.views.can_manage", return_value=False)
@mock.patch("learning.mentors.views.can_request", return_value=True)
class MentorApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.pilot = _user("talisker", 2124705658, 11)
        self.orion = _user("orion", 93672441, 22)
        self.profile = _mentor(self.orion)
        self.mc = MentorClass.objects.create(
            slug="multi-boxing",
            title="Multi-boxing",
            status=MentorClass.STATUS_PUBLISHED,
            author=self.orion,
            requirements=[{"kind": "accounts", "value": "2"}],
        )
        MentorClassTeacher.objects.create(
            mentor_class=self.mc, mentor=self.profile
        )

    def test_home_lists_the_mentor(self, *_):
        response = self.client.get(BASE, **auth_headers(self.pilot))
        self.assertEqual(200, response.status_code)
        mentors = response.json()["mentors"]
        self.assertEqual(["Orion"], [m["person"]["name"] for m in mentors])
        self.assertEqual("multi-boxing", mentors[0]["classes"][0]["slug"])

    def test_class_page_checks_requirements(self, *_):
        response = self.client.get(
            f"{BASE}/classes/multi-boxing", **auth_headers(self.pilot)
        )
        body = response.json()
        self.assertFalse(body["all_met"])
        self.assertEqual("You have 1", body["requirements"][0]["detail"])

    def test_request_blocked_by_requirements(self, *_):
        response = self.client.post(
            f"{BASE}/requests",
            data={
                "mentor_id": self.profile.pk,
                "class_id": self.mc.pk,
                "weekday_brackets": ["USTZ"],
                "weekend_brackets": ["USTZ"],
                "days": [0, 1, 2, 3, 4, 5, 6],
            },
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("accounts", response.json()["detail"])

    def test_mentoring_is_for_mentors(self, *_):
        response = self.client.get(
            f"{BASE}/mentoring", **auth_headers(self.pilot)
        )
        self.assertEqual(403, response.status_code)
        response = self.client.get(
            f"{BASE}/mentoring", **auth_headers(self.orion)
        )
        self.assertEqual(200, response.status_code)

    def test_admin_needs_learning_manager(self, *_):
        response = self.client.get(f"{BASE}/admin", **auth_headers(self.orion))
        self.assertEqual(403, response.status_code)

    def _class_body(self, **changes):
        body = {
            "title": "Plexing for ISK",
            "minutes": 30,
            "where": "in_space",
            "requirements": [{"kind": "alliance_days", "value": "7"}],
            "cover_image_url": "/images/hek-campaign.webp",
        }
        body.update(changes)
        return body

    def test_mentors_cannot_create_classes(self, *_):
        response = self.client.post(
            f"{BASE}/classes",
            data=self._class_body(),
            content_type="application/json",
            **auth_headers(self.orion),
        )
        self.assertEqual(403, response.status_code)
        response = self.client.get(
            f"{BASE}/classes/{self.mc.pk}/edit", **auth_headers(self.orion)
        )
        self.assertEqual(403, response.status_code)

    def test_manager_sets_up_a_class_with_a_cover(self, *_):
        with mock.patch(
            "learning.mentors.views.can_manage", return_value=True
        ):
            options = self.client.get(
                f"{BASE}/admin/class-options", **auth_headers(self.pilot)
            )
            self.assertEqual(200, options.status_code)
            covers = [c["url"] for c in options.json()["covers"]]
            self.assertIn("", covers)
            self.assertIn("/images/hek-campaign.webp", covers)

            response = self.client.post(
                f"{BASE}/classes",
                data=self._class_body(cover_image_url="/etc/passwd"),
                content_type="application/json",
                **auth_headers(self.pilot),
            )
            self.assertEqual(400, response.status_code)

            response = self.client.post(
                f"{BASE}/classes",
                data=self._class_body(),
                content_type="application/json",
                **auth_headers(self.pilot),
            )
            self.assertEqual(201, response.status_code)
            class_id = response.json()["id"]
            mc = MentorClass.objects.get(pk=class_id)
            self.assertEqual(MentorClass.STATUS_DRAFT, mc.status)
            self.assertEqual("/images/hek-campaign.webp", mc.cover_image_url)
            # The manager doesn't become a teacher by setting it up.
            self.assertFalse(mc.teachers.exists())

            admin = self.client.get(
                f"{BASE}/admin", **auth_headers(self.pilot)
            ).json()
            self.assertEqual(
                [class_id], [row["id"] for row in admin["drafts"]]
            )

            response = self.client.post(
                f"{BASE}/classes/{class_id}/teachers",
                data={"character_name": "orion"},
                content_type="application/json",
                **auth_headers(self.pilot),
            )
            self.assertEqual(200, response.status_code, response.json())

        # An invited mentor can take a class before it is published.
        response = self.client.post(
            f"{BASE}/classes/{class_id}/teach", **auth_headers(self.orion)
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            MentorClassTeacher.STATUS_ACCEPTED,
            mc.teachers.get(mentor=self.profile).status,
        )

    def test_class_page_carries_its_cover(self, *_):
        self.mc.cover_image_url = "/images/home-auga-cover.jpg"
        self.mc.save()
        detail = self.client.get(
            f"{BASE}/classes/{self.mc.slug}", **auth_headers(self.pilot)
        )
        self.assertEqual(200, detail.status_code)
        self.assertEqual(
            "/images/home-auga-cover.jpg", detail.json()["cover_image_url"]
        )

    def test_bot_endpoints_need_the_service_account(self, *_):
        req = MentorRequest.objects.create(
            pilot=self.pilot, mentor=self.profile, mentor_class=self.mc
        )
        response = self.client.post(
            f"{BASE}/requests/{req.pk}/discord-pass",
            data={"discord_user_id": 22},
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(403, response.status_code)

        bot = User.objects.create_user(username="bot", password="x")
        bot.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="users", codename="service_account"
            )
        )
        response = self.client.post(
            f"{BASE}/requests/{req.pk}/discord-pass",
            data={"discord_user_id": 22},
            content_type="application/json",
            **auth_headers(bot),
        )
        self.assertEqual(200, response.status_code)
        req.refresh_from_db()
        self.assertEqual(MentorRequest.STATUS_EXPIRED, req.status)


class GuideEditorTestCase(TestCase):
    """The guides admin can attach a mentor class but not rewrite it."""

    def setUp(self):
        self.manager = User.objects.create_superuser("manager", password="x")
        self.client = Client()
        self.mc = MentorClass.objects.create(
            slug="small-gang",
            title="Small gang",
            status=MentorClass.STATUS_PUBLISHED,
        )
        service.sync_learning(self.mc)
        self.mc.refresh_from_db()

    def _body(self, **changes):
        body = {
            "slug": self.mc.learning.slug,
            "title": "Renamed",
            "summary": "",
            "url": "/somewhere/",
            "content_kind": "guide",
            "thumbnail_url": "",
            "estimated_minutes": None,
            "published": True,
        }
        body.update(changes)
        return body

    def test_editing_a_mentor_class_row_is_refused(self):
        response = self.client.put(
            f"/api/learning/manage/guides/{self.mc.learning.slug}",
            self._body(),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(400, response.status_code)
        self.mc.learning.refresh_from_db()
        self.assertEqual("Small gang", self.mc.learning.title)

    def test_a_guide_cannot_be_created_as_a_mentor_class(self):
        response = self.client.post(
            "/api/learning/manage/guides",
            self._body(slug="fake-class", content_kind="mentor_class"),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(400, response.status_code)
