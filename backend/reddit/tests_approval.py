from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.utils import timezone

from reddit import approval
from reddit.corporation_posts import post_settings, save_post_settings
from reddit.models import RedditPostChangeRequest, RedditPostTemplate
from reddit.tests_corporation_posts import CorporationPostTestCase

PENDING = RedditPostChangeRequest.PENDING


class ApprovalTestCase(CorporationPostTestCase):
    """Shared fixtures: an approving superuser and the CEO's autosave."""

    def setUp(self):
        super().setUp()
        self.boss = User.objects.create_superuser("boss", "b@x", "pw")

    def approved_post(self, **fields):
        return self.make_post(
            approved=True,
            approved_by=self.boss,
            approved_at=timezone.now(),
            **fields,
        )

    def edit(self, title="Join the Rat", content="We fly together.", **kw):
        kw.setdefault("delivery_method", "alliance")
        return save_post_settings(
            self.corporation, title, content, user=self.user, **kw
        )


class ChangeRequestTestCase(ApprovalTestCase):

    def test_approved_words_keep_going_out_while_a_change_waits(self):
        post = self.approved_post()
        self.edit(content="We fly together.\n\nNow with cake.")
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertEqual("We fly together.", post.content)
        change = approval.pending_change(post)
        self.assertEqual("We fly together.\n\nNow with cake.", change.content)
        self.assertEqual(self.user, change.submitted_by)

    def test_autosaves_update_one_request(self):
        post = self.approved_post()
        for text in ("We fly", "We fly t", "We fly tonight."):
            self.edit(content=text)
        self.assertEqual(1, post.change_requests.count())
        self.assertEqual("We fly tonight.", post.change_requests.get().content)

    def test_editing_back_to_the_approved_words_withdraws_it(self):
        post = self.approved_post()
        self.edit(content="Something else")
        self.edit(content="We fly together.")
        self.assertIsNone(approval.pending_change(post))
        self.assertEqual(
            RedditPostChangeRequest.WITHDRAWN,
            post.change_requests.get().status,
        )

    def test_crlf_body_is_not_an_edit(self):
        post = self.approved_post(content="One\r\n\r\nTwo")
        self.edit(content="One\n\nTwo", paused=True)
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertTrue(post.paused)
        self.assertFalse(post.change_requests.exists())

    def test_ceo_sees_and_keeps_editing_their_waiting_change(self):
        self.approved_post()
        self.edit(title="Fresh title")
        data = post_settings(self.corporation, self.user)
        self.assertEqual("Fresh title", data["title"])
        self.assertTrue(data["approved"])
        self.assertTrue(data["change_pending"])
        self.assertIsNotNone(data["change_submitted_at"])

    def test_approving_puts_the_change_live(self):
        post = self.approved_post()
        change = self.edit(title="Fresh title") and approval.pending_change(
            post
        )
        self.assertTrue(approval.approve(change, self.boss))
        post.refresh_from_db()
        self.assertEqual("Fresh title", post.title)
        self.assertTrue(post.approved)
        self.assertEqual(self.boss, post.approved_by)
        self.assertFalse(
            post_settings(self.corporation, self.user)["change_pending"]
        )
        self.assertFalse(approval.approve(change, self.boss))

    def test_rejecting_keeps_the_approved_words_and_tells_the_ceo(self):
        post = self.approved_post()
        self.edit(title="Fresh title")
        change = approval.pending_change(post)
        self.assertTrue(approval.reject(change, self.boss, "Too spicy"))
        post.refresh_from_db()
        self.assertEqual("Join the Rat", post.title)
        data = post_settings(self.corporation, self.user)
        self.assertEqual("Join the Rat", data["title"])
        self.assertEqual("Too spicy", data["change_rejected_note"])
        # Editing again starts a new request and clears the rejection.
        self.edit(title="Milder title")
        data = post_settings(self.corporation, self.user)
        self.assertIsNone(data["change_rejected_note"])
        self.assertTrue(data["change_pending"])

    def test_unapproved_post_takes_edits_and_waits_for_first_approval(self):
        post = self.make_post()
        self.edit(title="Fresh title")
        post.refresh_from_db()
        self.assertEqual("Fresh title", post.title)
        change = approval.pending_change(post)
        self.assertEqual("Fresh title", change.title)
        # Not a "change" to the CEO: there are no approved words yet.
        self.assertFalse(
            post_settings(self.corporation, self.user)["change_pending"]
        )
        self.assertTrue(approval.approve(change, self.boss))
        post.refresh_from_db()
        self.assertTrue(post.approved)

    def test_reminder_posts_need_no_review(self):
        post = self.approved_post(delivery_method="discord_reminder")
        self.edit(title="Fresh title", delivery_method="discord_reminder")
        post.refresh_from_db()
        self.assertEqual("Fresh title", post.title)
        self.assertFalse(post.approved)
        self.assertIsNone(approval.pending_change(post))
        # Switching to automatic posting puts it up for approval.
        self.edit(title="Fresh title", delivery_method="alliance")
        self.assertIsNotNone(approval.pending_change(post))

    def test_approve_action_approves_the_waiting_change(self):
        post = self.approved_post()
        self.edit(title="Fresh title")
        self.assertTrue(approval.approve_template(post, self.boss))
        post.refresh_from_db()
        self.assertEqual("Fresh title", post.title)

    def test_approve_action_on_a_post_with_nothing_waiting(self):
        post = self.make_post()
        self.assertTrue(approval.approve_template(post, self.boss))
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertFalse(approval.approve_template(post, self.boss))


@override_settings(
    REDDIT_REVIEWER_DISCORD_IDS=["124039469488799746"],
    MINMATAR_ADMIN_BASE_URL="https://api.example.org",
)
@patch("reddit.approval.queue_dm")
class ReviewerNotificationTestCase(ApprovalTestCase):
    def test_reviewers_hear_once_the_edit_settles(self, queue_dm):
        post = self.approved_post()
        self.edit(title="Fresh title")
        change = approval.pending_change(post)
        self.assertEqual(0, approval.notify_reviewers())
        later = timezone.now() + approval.SETTLE + timedelta(seconds=1)
        self.assertEqual(1, approval.notify_reviewers(later))
        queue_dm.assert_called_once()
        self.assertEqual("124039469488799746", queue_dm.call_args.args[0])
        message = queue_dm.call_args.kwargs["message"]
        self.assertIn("Reddit post change to review: Rattini Tribe", message)
        self.assertIn("Was: Join the Rat", message)
        self.assertIn(
            "https://api.example.org/admin/reddit/redditpostchangerequest/"
            f"{change.pk}/change/",
            message,
        )
        self.assertEqual(0, approval.notify_reviewers(later))

    def test_new_posts_are_announced_as_new(self, queue_dm):
        self.edit(title="Brand new")
        later = timezone.now() + approval.SETTLE + timedelta(seconds=1)
        approval.notify_reviewers(later)
        self.assertIn(
            "New Reddit post to approve",
            queue_dm.call_args.kwargs["message"],
        )

    def test_editing_after_the_dm_sends_an_update(self, queue_dm):
        post = self.approved_post()
        self.edit(title="Fresh title")
        change = approval.pending_change(post)
        RedditPostChangeRequest.objects.filter(pk=change.pk).update(
            updated_at=timezone.now() - approval.SETTLE * 2,
            notified_at=timezone.now() - approval.SETTLE,
        )
        self.assertEqual(0, approval.notify_reviewers())
        self.edit(title="Fresher title")
        later = timezone.now() + approval.SETTLE + timedelta(seconds=1)
        self.assertEqual(1, approval.notify_reviewers(later))
        self.assertIn(
            "Reddit post change updated",
            queue_dm.call_args.kwargs["message"],
        )

    def test_unchanged_autosave_does_not_re_notify(self, queue_dm):
        post = self.approved_post()
        self.edit(title="Fresh title")
        later = timezone.now() + approval.SETTLE + timedelta(seconds=1)
        approval.notify_reviewers(later)
        self.edit(title="Fresh title", paused=True)
        self.assertEqual(
            0, approval.notify_reviewers(later + approval.SETTLE * 2)
        )
        self.assertEqual(1, queue_dm.call_count)
        self.assertTrue(post.change_requests.exists())


@patch(
    "reddit.admin.reddit_client.get_link_flairs",
    return_value=[{"id": "f1", "text": "Recruiting"}],
)
class ApprovalAdminTestCase(ApprovalTestCase):
    """Through the admin pages, the way a superuser approves."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.boss)

    def template_form(self, template, **data):
        values = {
            "corporation": template.corporation_id,
            "subreddit": template.subreddit,
            "title": template.title,
            # As a browser sends a textarea.
            "content": template.content.replace("\n", "\r\n"),
            "priority": template.priority,
            "posting_window": template.posting_window,
            "delivery_method": template.delivery_method,
            "flair_id": "f1",
            "posts-TOTAL_FORMS": "0",
            "posts-INITIAL_FORMS": "0",
            "_save": "Save",
        }
        values.update(data)
        return values

    def test_ticking_approved_saves(self, flairs):
        post = self.make_post(content="We fly.\n\nTogether.")
        url = f"/admin/reddit/redditposttemplate/{post.pk}/change/"
        response = self.client.post(
            url, self.template_form(post, approved="on")
        )
        self.assertEqual(302, response.status_code)
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertEqual(self.boss, post.approved_by)
        # The CRLF from the textarea was not stored as a change.
        self.assertEqual("We fly.\n\nTogether.", post.content)
        # The CEO autosaving the same words keeps the approval.
        self.edit(content="We fly.\n\nTogether.")
        post.refresh_from_db()
        self.assertTrue(post.approved)

    def test_ticking_approved_closes_the_first_approval_request(self, flairs):
        self.edit(title="Brand new")
        post = RedditPostTemplate.objects.get(corporation=self.corporation)
        url = f"/admin/reddit/redditposttemplate/{post.pk}/change/"
        self.client.post(url, self.template_form(post, approved="on"))
        self.assertIsNone(approval.pending_change(post))
        self.assertEqual(
            RedditPostChangeRequest.APPROVED,
            post.change_requests.get().status,
        )

    def test_change_request_page_shows_the_diff(self, flairs):
        post = self.approved_post(content="Line one\nLine two")
        self.edit(content="Line one\nLine 2")
        change = approval.pending_change(post)
        response = self.client.get(
            f"/admin/reddit/redditpostchangerequest/{change.pk}/change/"
        )
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "-Line two")
        self.assertContains(response, "+Line 2")

    def test_approving_from_the_change_request_page(self, flairs):
        post = self.approved_post()
        self.edit(title="Fresh title")
        change = approval.pending_change(post)
        response = self.client.post(
            f"/admin/reddit/redditpostchangerequest/{change.pk}/change/",
            {"decision": "approve", "review_note": "", "_save": "Save"},
        )
        self.assertEqual(302, response.status_code)
        post.refresh_from_db()
        self.assertEqual("Fresh title", post.title)
        # Reviewed requests are read-only.
        response = self.client.get(
            f"/admin/reddit/redditpostchangerequest/{change.pk}/change/"
        )
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, 'name="decision"')

    def test_rejecting_from_the_change_request_page(self, flairs):
        post = self.approved_post()
        self.edit(title="Fresh title")
        change = approval.pending_change(post)
        self.client.post(
            f"/admin/reddit/redditpostchangerequest/{change.pk}/change/",
            {"decision": "reject", "review_note": "Nope", "_save": "Save"},
        )
        change.refresh_from_db()
        self.assertEqual(RedditPostChangeRequest.REJECTED, change.status)
        self.assertEqual("Nope", change.review_note)
        post.refresh_from_db()
        self.assertEqual("Join the Rat", post.title)

    def test_template_list_flags_waiting_changes(self, flairs):
        self.approved_post()
        self.edit(title="Fresh title")
        response = self.client.get("/admin/reddit/redditposttemplate/")
        self.assertEqual(200, response.status_code)
