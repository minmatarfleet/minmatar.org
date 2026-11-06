from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import Client
from django.utils import timezone

from app.testing import auth_headers
from reddit import approval
from reddit.models import (
    RedditPost,
    RedditPostChangeRequest,
    RedditSchedule,
)
from reddit.tests_approval import ApprovalTestCase

BASE = "/api/reddit/review"


class ReviewApiTestCase(ApprovalTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.reviewer = User.objects.create_user("reviewer", "r@x", "pw")
        self.reviewer.user_permissions.add(
            Permission.objects.get(
                codename="change_redditpostchangerequest",
                content_type__app_label="reddit",
            )
        )
        self.headers = auth_headers(self.reviewer)
        self.link_discord()

    def get(self, path, headers=None):
        return self.client.get(
            BASE + path, **(headers if headers is not None else self.headers)
        )

    def post(self, path, body=None, headers=None):
        return self.client.post(
            BASE + path,
            body or {},
            content_type="application/json",
            **(headers if headers is not None else self.headers),
        )

    def pending(self):
        post = self.approved_post()
        self.edit(content="Now with cake.")
        return post, approval.pending_change(post)


class ReviewPermissionTestCase(ReviewApiTestCase):
    def test_everything_is_forbidden_without_the_feature(self):
        plain = auth_headers(User.objects.create_user("plain", "p@x", "pw"))
        post, change = self.pending()
        for method, path in (
            ("get", "/queue"),
            ("get", "/rotation"),
            ("post", f"/changes/{change.pk}/approve"),
            ("post", f"/changes/{change.pk}/reject"),
            ("post", f"/templates/{post.pk}/approve"),
            ("post", f"/templates/{post.pk}/submit"),
            ("post", f"/templates/{post.pk}/link-discord"),
            ("post", "/schedules/1/publish"),
            ("post", "/schedules/1/regenerate"),
        ):
            with self.subTest(path=path):
                response = getattr(self, method)(path, headers=plain)
                self.assertEqual(403, response.status_code)
        change.refresh_from_db()
        self.assertEqual(RedditPostChangeRequest.PENDING, change.status)


@patch("reddit.scheduling.queue_dm")
class ReviewDecisionTestCase(ReviewApiTestCase):
    def test_queue_shows_the_change_beside_the_current_text(self, unused_dm):
        change = self.pending()[1]
        item = self.get("/queue").json()["items"][0]
        self.assertEqual(change.pk, item["change_id"])
        self.assertEqual("We fly together.", item["current_content"])
        self.assertEqual("Now with cake.", item["requested_content"])
        self.assertFalse(item["first_approval"])

    def test_queue_lists_an_unapproved_template_without_a_change(
        self, unused_dm
    ):
        post = self.make_post()
        items = self.get("/queue").json()["items"]
        self.assertEqual([post.pk], [i["template_id"] for i in items])
        self.assertTrue(items[0]["first_approval"])

    def test_approve_puts_the_words_live_and_dms_the_ceo(self, queue_dm):
        post, change = self.pending()
        response = self.post(f"/changes/{change.pk}/approve")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["changed"])
        post.refresh_from_db()
        self.assertEqual("Now with cake.", post.content)
        self.assertEqual(self.reviewer, post.approved_by)
        queue_dm.assert_called_once()
        self.assertEqual(4242, queue_dm.call_args.args[0])
        again = self.post(f"/changes/{change.pk}/approve").json()
        self.assertFalse(again["changed"])
        queue_dm.assert_called_once()

    def test_reject_keeps_the_old_words_and_tells_the_ceo_why(self, queue_dm):
        post, change = self.pending()
        response = self.post(
            f"/changes/{change.pk}/reject", {"note": "Too many cakes"}
        )
        self.assertTrue(response.json()["changed"])
        post.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual("We fly together.", post.content)
        self.assertEqual("Too many cakes", change.review_note)
        self.assertIn(
            "Too many cakes", queue_dm.call_args.kwargs["messages"][0]
        )

    def test_approve_a_template_with_no_change(self, queue_dm):
        post = self.make_post()
        response = self.post(f"/templates/{post.pk}/approve")
        self.assertTrue(response.json()["changed"])
        post.refresh_from_db()
        self.assertTrue(post.approved)
        queue_dm.assert_called_once()

    def test_unknown_ids_are_404(self, unused_dm):
        self.assertEqual(404, self.post("/changes/999/approve").status_code)
        self.assertEqual(404, self.post("/templates/999/approve").status_code)


class ReviewRotationTestCase(ReviewApiTestCase):
    def test_rotation_lists_posts_and_publish_confirms_the_draft(self):
        post = self.approved_post()
        month = RedditSchedule.objects.create(
            month=timezone.now().date().replace(day=1),
            status=RedditSchedule.DRAFT,
        )
        when = timezone.now() + timezone.timedelta(days=10)
        RedditPost.objects.create(
            template=post,
            schedule=month,
            slot_date=when.date(),
            scheduled_for=when,
            status=RedditPost.DRAFT,
        )
        with patch("reddit.review_router.schedule.refresh_drafts"):
            data = self.get("/rotation").json()
        listed = data["months"][0]
        self.assertEqual(
            "Rattini Tribe", listed["posts"][0]["corporation_name"]
        )
        with patch(
            "reddit.review_router.schedule.publish", return_value=1
        ) as publish:
            result = self.post(f"/schedules/{month.pk}/publish").json()
        self.assertTrue(result["ok"])
        publish.assert_called_once()

    def test_manual_submit_uses_the_existing_service(self):
        post = self.approved_post()
        sent = RedditPost(status=RedditPost.POSTED)
        with patch(
            "reddit.review_router.RedditService.post_recriutment_ad",
            return_value=sent,
        ) as submit:
            result = self.post(f"/templates/{post.pk}/submit").json()
        self.assertTrue(result["ok"])
        submit.assert_called_once_with(post)

    def test_link_to_discord_needs_a_channel_and_a_posted_slot(self):
        post = self.approved_post()
        result = self.post(f"/templates/{post.pk}/link-discord").json()
        self.assertFalse(result["ok"])
        self.assertIn("channel", result["detail"])
