from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings

from app.test import TestCase
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from reddit.admin import RedditScheduledPostAdminForm
from reddit.client import RedditClient, normalize_subreddit
from reddit.markdown import check_reddit_markdown
from reddit.corporation_posts import PostSettingsError, save_post_settings
from reddit.models import RedditAccount, RedditScheduledPost
from reddit.oauth import RedditOAuthError
from reddit.scheduling import (
    ACCOUNT_INVALID,
    DISCORD_MESSAGE_LIMIT,
    NO_ACCOUNT,
    NOT_APPROVED,
    POST_FAILED,
    deliver,
    due_posts,
    next_slot,
    reminder_messages,
    run_scheduled_posts,
)

# Thursday 2026-10-15, 18:00 UTC.
THURSDAY_1800 = datetime(2026, 10, 15, 18, 0, tzinfo=dt_timezone.utc)
SUBMITTED = {
    "url": "https://www.reddit.com/r/evejobs/comments/x/y/",
    "id": "x",
}


class CorporationPostTestCase(TestCase):
    """Shared fixtures: a corporation whose CEO is self.user."""

    def setUp(self):
        super().setUp()
        self.ceo = EveCharacter.objects.create(
            character_id=91000001,
            character_name="Rat CEO",
            user=self.user,
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Rattini Tribe", ceo=self.ceo
        )

    def make_post(self, **fields):
        values = {
            "corporation": self.corporation,
            "subreddit": "evejobs",
            "title": "Join the Rat",
            "content": "We fly together.",
            "posting_day": "thursday",
            "posting_time": time(17, 0),
        }
        values.update(fields)
        return RedditScheduledPost.objects.create(**values)

    def link_reddit(self, **fields):
        values = {
            "user": self.user,
            "reddit_username": "BearThatCares",
            "refresh_token": "refresh",
        }
        values.update(fields)
        return RedditAccount.objects.create(**values)

    def link_discord(self):
        return DiscordUser.objects.create(
            id=4242, discord_tag="ceo", user=self.user
        )


class ScheduleTestCase(CorporationPostTestCase):
    """When a post is due, and that it is handled once per slot."""

    def test_due_after_its_time_on_its_day(self):
        post = self.make_post()
        self.assertEqual(
            [(post, THURSDAY_1800 - timedelta(hours=1))],
            due_posts(THURSDAY_1800),
        )

    def test_not_due_before_its_time(self):
        self.make_post(posting_time=time(19, 0))
        self.assertEqual([], due_posts(THURSDAY_1800))

    def test_not_due_on_other_days(self):
        self.make_post(posting_day="friday")
        self.assertEqual([], due_posts(THURSDAY_1800))

    def test_unscheduled_drafts_are_never_due(self):
        self.make_post(posting_day="")
        self.make_post(
            corporation=None, subreddit="", title="No subreddit yet"
        )
        self.assertEqual([], due_posts(THURSDAY_1800))

    def test_late_slot_still_runs_after_midnight(self):
        # 23:55 Thursday is caught by the 00:00 Friday run.
        self.make_post(posting_time=time(23, 55))
        friday = datetime(2026, 10, 16, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(1, len(due_posts(friday)))

    def test_slot_missed_by_more_than_the_catch_up_window_is_skipped(self):
        self.make_post(posting_time=time(1, 0))
        self.assertEqual([], due_posts(THURSDAY_1800))

    def test_old_daily_task_post_today_is_not_repeated(self):
        # Deploy day: the old 13:00 task already posted this alliance post.
        self.make_post(
            corporation=None,
            posting_time=time(13, 0),
            last_post_at=THURSDAY_1800.replace(hour=13, minute=0, second=5),
        )
        self.assertEqual([], due_posts(THURSDAY_1800))

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_each_slot_is_delivered_once(self, deliver_mock):
        self.make_post()
        self.assertEqual(["reminded"], run_scheduled_posts(THURSDAY_1800))
        self.assertEqual(
            [], run_scheduled_posts(THURSDAY_1800 + timedelta(minutes=15))
        )
        self.assertEqual(1, deliver_mock.call_count)

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_runs_again_next_week(self, deliver_mock):
        self.make_post()
        run_scheduled_posts(THURSDAY_1800)
        run_scheduled_posts(THURSDAY_1800 + timedelta(days=7))
        self.assertEqual(2, deliver_mock.call_count)

    def test_next_slot(self):
        post = self.make_post()
        self.assertEqual(
            THURSDAY_1800 - timedelta(hours=1),
            next_slot(post, THURSDAY_1800),
        )
        post.last_scheduled_on = THURSDAY_1800.date()
        self.assertEqual(
            THURSDAY_1800 + timedelta(days=7, hours=-1),
            next_slot(post, THURSDAY_1800),
        )


@patch("reddit.scheduling.DiscordClient")
@patch.object(RedditClient, "submit_post", return_value=SUBMITTED)
class DeliverTestCase(CorporationPostTestCase):
    """Automatic posting vs. the Discord reminder fallback."""

    def setUp(self):
        super().setUp()
        self.link_discord()

    def test_reminder_method_sends_dm_and_does_not_post(
        self, submit_post, discord
    ):
        post = self.make_post()
        self.assertEqual("reminded", deliver(post))
        submit_post.assert_not_called()
        (dm_user,) = {c.args[0] for c in discord().send_dm.call_args_list}
        self.assertEqual("4242", dm_user)
        post.refresh_from_db()
        self.assertIsNotNone(post.last_reminder_at)

    @patch("reddit.scheduling.RedditClient")
    def test_automatic_posts_as_the_ceo_account(
        self, client_class, submit_post, discord
    ):
        client_class.return_value.submit_post.return_value = SUBMITTED
        account = self.link_reddit()
        post = self.make_post(delivery_method="automatic", approved=True)
        self.assertEqual("posted", deliver(post))
        client_class.assert_called_once_with(account)
        discord().send_dm.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(SUBMITTED["url"], post.last_reddit_post_url)

    def _reminder_reason(self, post, discord):
        with patch(
            "reddit.scheduling.reminder_messages", return_value=["hi"]
        ) as messages:
            self.assertEqual("reminded", deliver(post))
        return messages.call_args.args[1]

    def test_unapproved_automatic_post_falls_back_to_reminder(
        self, submit_post, discord
    ):
        self.link_reddit()
        post = self.make_post(delivery_method="automatic", approved=False)
        self.assertEqual(NOT_APPROVED, self._reminder_reason(post, discord))
        submit_post.assert_not_called()

    def test_automatic_without_linked_account_reminds(
        self, submit_post, discord
    ):
        post = self.make_post(delivery_method="automatic", approved=True)
        self.assertEqual(NO_ACCOUNT, self._reminder_reason(post, discord))
        submit_post.assert_not_called()

    def test_automatic_with_revoked_account_reminds(
        self, submit_post, discord
    ):
        self.link_reddit(token_invalid=True)
        post = self.make_post(delivery_method="automatic", approved=True)
        self.assertEqual(ACCOUNT_INVALID, self._reminder_reason(post, discord))
        submit_post.assert_not_called()

    def test_failed_automatic_post_reminds(self, submit_post, discord):
        submit_post.return_value = None
        self.link_reddit()
        post = self.make_post(delivery_method="automatic", approved=True)
        self.assertEqual(POST_FAILED, self._reminder_reason(post, discord))

    def test_alliance_post_uses_alliance_account(self, submit_post, discord):
        post = self.make_post(
            corporation=None, delivery_method="automatic", approved=True
        )
        with patch("reddit.scheduling.RedditClient") as client_class:
            client_class.return_value.submit_post.return_value = SUBMITTED
            self.assertEqual("posted", deliver(post))
        client_class.assert_called_once_with()

    def test_unapproved_alliance_post_is_skipped(self, submit_post, discord):
        post = self.make_post(corporation=None, delivery_method="automatic")
        self.assertEqual("skipped", deliver(post))
        submit_post.assert_not_called()
        discord().send_dm.assert_not_called()


class NoDiscordTestCase(CorporationPostTestCase):
    @patch("reddit.scheduling.DiscordClient")
    def test_ceo_without_discord_is_skipped(self, discord):
        post = self.make_post()
        self.assertEqual("skipped", deliver(post))
        discord().send_dm.assert_not_called()


class ReminderMessageTestCase(CorporationPostTestCase):
    def test_long_body_is_split_into_discord_sized_messages(self):
        body = "\n".join(f"Line {i} " + "x" * 80 for i in range(100))
        post = self.make_post(content=body)
        messages = reminder_messages(post, NOT_APPROVED)
        self.assertGreater(len(messages), 3)
        for message in messages:
            self.assertLessEqual(len(message), DISCORD_MESSAGE_LIMIT)
        self.assertIn("r/evejobs/submit", messages[0])
        self.assertIn("waiting for approval", messages[0])
        self.assertIn(
            "/alliance/corporations/rattini-tribe/#settings", messages[0]
        )
        joined = "".join(m.strip("`\n") for m in messages[1:])
        self.assertIn("Line 99", joined)

    def test_code_fences_in_body_do_not_break_the_message(self):
        post = self.make_post(content="```\ncode\n```")
        body = reminder_messages(post)[1]
        self.assertEqual(2, body.count("```"))


class SaveSettingsTestCase(CorporationPostTestCase):
    def test_creates_an_unscheduled_draft(self):
        post = save_post_settings(
            self.corporation, " Title ", "Body", "automatic"
        )
        self.assertEqual("Title", post.title)
        self.assertEqual("", post.posting_day)
        self.assertFalse(post.approved)

    def test_editing_words_withdraws_approval(self):
        post = self.make_post(approved=True, approved_by=self.user)
        save_post_settings(
            self.corporation, "New title", post.content, "automatic"
        )
        post.refresh_from_db()
        self.assertFalse(post.approved)
        self.assertIsNone(post.approved_by)

    def test_changing_only_delivery_keeps_approval(self):
        post = self.make_post(approved=True)
        save_post_settings(
            self.corporation, post.title, post.content, "automatic"
        )
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertEqual("automatic", post.delivery_method)

    def test_rejects_bad_input(self):
        for args, code in (
            (("", "Body", "automatic"), "title_required"),
            (("Title", "  ", "automatic"), "content_required"),
            (("T" * 251, "Body", "automatic"), "title_too_long"),
            (("Title", "Body", "carrier_pigeon"), "invalid_delivery_method"),
        ):
            with self.assertRaises(PostSettingsError) as raised:
                save_post_settings(self.corporation, *args)
            self.assertEqual(code, raised.exception.code)


class RouterTestCase(CorporationPostTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.url = (
            f"/api/reddit/corporations/{self.corporation.corporation_id}/post"
        )

    def auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    def other_user_token(self):
        other = User.objects.create(username="not-ceo")
        return jwt.encode(
            {"user_id": other.id}, settings.SECRET_KEY, algorithm="HS256"
        )

    def test_ceo_reads_settings(self):
        self.make_post(approved=True)
        self.link_reddit()
        body = self.client.get(self.url, **self.auth()).json()
        self.assertTrue(body["exists"])
        self.assertEqual("thursday", body["posting_day"])
        self.assertEqual("17:00", body["posting_time"])
        self.assertEqual("ready", body["automatic_status"])
        self.assertEqual("BearThatCares", body["reddit_account"]["username"])
        self.assertNotIn("refresh_token", str(body))

    def test_only_the_ceo_can_read_or_edit(self):
        other = self.other_user_token()
        self.assertEqual(
            403, self.client.get(self.url, **self.auth(other)).status_code
        )
        response = self.client.put(
            self.url,
            data={
                "title": "x",
                "content": "y",
                "delivery_method": "automatic",
            },
            content_type="application/json",
            **self.auth(other),
        )
        self.assertEqual(403, response.status_code)
        self.assertFalse(RedditScheduledPost.objects.exists())

    def test_superuser_who_is_not_ceo_cannot_edit(self):
        other = self.other_user_token()
        User.objects.filter(username="not-ceo").update(is_superuser=True)
        self.assertEqual(
            403, self.client.get(self.url, **self.auth(other)).status_code
        )

    def test_ceo_saves_settings(self):
        response = self.client.put(
            self.url,
            data={
                "title": "Join the Rat",
                "content": "# Rattini\nWe fly.",
                "delivery_method": "discord_reminder",
            },
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("unscheduled", response.json()["automatic_status"])
        post = RedditScheduledPost.objects.get(corporation=self.corporation)
        self.assertEqual("# Rattini\nWe fly.", post.content)

    def test_invalid_settings_are_a_400(self):
        response = self.client.put(
            self.url,
            data={"title": "", "content": "y", "delivery_method": "automatic"},
            content_type="application/json",
            **self.auth(),
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("title_required", response.json()["detail"])

    def test_member_access_reports_settings_tab(self):
        body = self.client.get(
            f"/api/eveonline/corporations/corporations/{self.corporation.corporation_id}/members/access",
            **self.auth(),
        ).json()
        self.assertTrue(body["can_edit_settings"])


@override_settings(
    WEB_LINK_URL="https://my.minmatar.org",
    REDDIT_CLIENT_ID="client-id",
    REDDIT_REDIRECT_URL="https://api.minmatar.org/api/reddit/callback",
)
class ConnectTestCase(CorporationPostTestCase):
    RETURN = (
        "https://my.minmatar.org/alliance/corporations/rattini-tribe/#settings"
    )

    def setUp(self):
        super().setUp()
        self.client = Client()

    def start(self, redirect_url=RETURN, token=None):
        return self.client.get(
            "/api/reddit/connect",
            {"redirect_url": redirect_url, "token": token or self.token},
        )

    def test_connect_redirects_to_reddit(self):
        response = self.start()
        self.assertEqual(302, response.status_code)
        self.assertTrue(
            response["Location"].startswith(
                "https://www.reddit.com/api/v1/authorize?"
            )
        )
        self.assertIn("duration=permanent", response["Location"])
        self.assertIn("scope=identity+submit+flair", response["Location"])

    def test_connect_refuses_other_sites(self):
        response = self.start("https://evil.example/steal")
        self.assertEqual(400, response.status_code)

    def test_connect_needs_a_valid_token(self):
        self.assertEqual(401, self.start(token="nope").status_code)

    def state(self):
        return self.client.session["reddit_oauth_state"]

    @patch("reddit.router.fetch_username", return_value="BearThatCares")
    @patch(
        "reddit.router.exchange_code",
        return_value={
            "access_token": "a",
            "refresh_token": "r",
            "scope": "identity submit flair",
        },
    )
    def test_callback_links_the_account(self, exchange, username):
        self.start()
        response = self.client.get(
            "/api/reddit/callback", {"code": "c", "state": self.state()}
        )
        self.assertEqual(
            "https://my.minmatar.org/alliance/corporations/rattini-tribe/"
            "?reddit=connected#settings",
            response["Location"],
        )
        account = RedditAccount.objects.get(user=self.user)
        self.assertEqual("BearThatCares", account.reddit_username)
        self.assertEqual("r", account.refresh_token)
        self.assertEqual(["identity", "submit", "flair"], account.scopes)

    @patch("reddit.router.exchange_code")
    def test_callback_rejects_wrong_state(self, exchange):
        self.start()
        response = self.client.get(
            "/api/reddit/callback", {"code": "c", "state": "forged"}
        )
        self.assertIn("reddit_error=state_mismatch", response["Location"])
        exchange.assert_not_called()
        self.assertFalse(RedditAccount.objects.exists())

    def test_callback_reports_denial(self):
        self.start()
        response = self.client.get(
            "/api/reddit/callback",
            {"error": "access_denied", "state": self.state()},
        )
        self.assertIn("reddit_error=denied", response["Location"])

    @patch(
        "reddit.router.exchange_code",
        side_effect=RedditOAuthError("invalid_grant"),
    )
    def test_callback_reports_exchange_failure(self, exchange):
        self.start()
        response = self.client.get(
            "/api/reddit/callback", {"code": "c", "state": self.state()}
        )
        self.assertIn("reddit_error=invalid_grant", response["Location"])

    @patch("reddit.router.revoke_refresh_token")
    def test_disconnect(self, revoke):
        self.link_reddit()
        response = self.client.delete(
            "/api/reddit/account", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(200, response.status_code)
        revoke.assert_called_once_with("refresh")
        self.assertFalse(RedditAccount.objects.exists())


class LinkedClientTestCase(CorporationPostTestCase):
    @patch(
        "reddit.client.refresh_access_token",
        side_effect=RedditOAuthError("invalid_grant"),
    )
    def test_revoked_refresh_token_marks_account_invalid(self, refresh):
        account = self.link_reddit()
        self.assertIsNone(RedditClient(account).get_access_token())
        account.refresh_from_db()
        self.assertTrue(account.token_invalid)

    @patch("reddit.client.refresh_access_token", return_value="fresh")
    def test_linked_account_uses_refresh_token(self, refresh):
        account = self.link_reddit()
        self.assertEqual("fresh", RedditClient(account).get_access_token())
        refresh.assert_called_once_with("refresh")

    def test_normalize_subreddit_keeps_leading_r(self):
        self.assertEqual("redditdev", normalize_subreddit("r/redditdev"))
        self.assertEqual("redditdev", normalize_subreddit("/r/redditdev/"))
        self.assertEqual("rattini", normalize_subreddit("rattini"))


class RedditMarkdownTestCase(TestCase):
    def codes(self, text):
        return [(p.code, p.line) for p in check_reddit_markdown(text)]

    def test_clean_reddit_markdown_has_no_problems(self):
        text = "\n".join(
            [
                "# Rattini Tribe",
                "",
                "*A cult* of **Minmatar** pilots. ~~Not~~ >!spoiler!< ^super",
                "",
                "## What we do",
                "- Daily fleets",
                "    - nested item",
                "1. Capitals",
                "",
                "> quoted",
                "",
                "| Day | Fleet |",
                "|---|---|",
                "| Mon | Roam |",
                "",
                "Line one with a hard break  ",
                "line two. Visit <https://minmatar.org> or [our site](https://minmatar.org).",
                "",
                "Inline `<b>code</b>` is fine.",
                "",
                "    <div>indented code</div>",
            ]
        )
        self.assertEqual([], self.codes(text))

    def test_unrenderable_syntax_blocks(self):
        text = "\n".join(
            [
                "Hello<br>world",
                "",
                "![logo](https://i.imgur.com/x.png)",
                "",
                "Note[^1]",
                "",
                "- [ ] todo",
                "",
                "<!-- hidden -->",
                "",
                "<center>**Big**</center>",
            ]
        )
        problems = check_reddit_markdown(text)
        self.assertEqual(
            [
                ("html", 1),
                ("image", 3),
                ("footnote", 5),
                ("task_list", 7),
                ("html", 9),
                ("html", 11),
            ],
            [(p.code, p.line) for p in problems],
        )
        self.assertTrue(all(p.blocking for p in problems))
        self.assertEqual("<br>", problems[0].excerpt)
        self.assertEqual("<center>", problems[-1].excerpt)

    def test_surprising_syntax_warns(self):
        text = "\n".join(
            [
                "#Recruiting",
                "",
                "First line",
                "second line",
                "",
                "```",
                "<b>code</b>",
                "```",
            ]
        )
        problems = check_reddit_markdown(text)
        self.assertEqual(
            [("heading_space", 1), ("soft_line_break", 4), ("fenced_code", 6)],
            [(p.code, p.line) for p in problems],
        )
        self.assertFalse(any(p.blocking for p in problems))

    def test_blocking_problems_sort_first_and_list_is_capped(self):
        text = "\n".join(["plain line"] * 40 + ["<b>late</b>"])
        problems = check_reddit_markdown(text)
        self.assertEqual(20, len(problems))
        self.assertEqual(("html", 41), (problems[0].code, problems[0].line))

    def test_save_rejects_unrenderable_markdown(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98000002, name="Markdown Corp"
        )
        with self.assertRaises(PostSettingsError) as raised:
            save_post_settings(
                corporation, "Title", "\n\nHi<br>there", "discord_reminder"
            )
        self.assertEqual("markdown_invalid", raised.exception.code)
        # Line numbers match the textarea, before trimming.
        self.assertEqual(3, raised.exception.problems[0]["line"])
        self.assertFalse(RedditScheduledPost.objects.exists())

    def test_save_allows_warnings(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98000003, name="Warning Corp"
        )
        post = save_post_settings(
            corporation, "Title", "one\ntwo", "discord_reminder"
        )
        self.assertEqual("one\ntwo", post.content)


class MarkdownRouterTestCase(CorporationPostTestCase):
    def test_put_returns_problems(self):
        response = Client().put(
            f"/api/reddit/corporations/{self.corporation.corporation_id}/post",
            data={
                "title": "Title",
                "content": "![x](https://i.imgur.com/x.png)",
                "delivery_method": "automatic",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        body = response.json()
        self.assertEqual("markdown_invalid", body["detail"])
        self.assertEqual("image", body["problems"][0]["code"])
        self.assertTrue(body["problems"][0]["blocking"])

    def test_get_reports_warnings_on_saved_content(self):
        self.make_post(content="one\ntwo")
        body = (
            Client()
            .get(
                f"/api/reddit/corporations/{self.corporation.corporation_id}/post",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            .json()
        )
        self.assertEqual(
            [
                {
                    "code": "soft_line_break",
                    "line": 2,
                    "excerpt": "two",
                    "blocking": False,
                }
            ],
            body["markdown_problems"],
        )


class AdminMarkdownTestCase(CorporationPostTestCase):
    def form(self, instance=None, **data):
        values = {
            "subreddit": "evejobs",
            "title": "Title",
            "content": "Fine",
            "posting_day": "thursday",
            "posting_time": "17:00",
            "delivery_method": "automatic",
        }
        values.update(data)
        return RedditScheduledPostAdminForm(data=values, instance=instance)

    def test_admin_rejects_new_unrenderable_content(self):
        form = self.form(content="<center>hi</center>")
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)

    @patch("reddit.admin.reddit_client.get_link_flairs", return_value=[])
    def test_admin_keeps_existing_content_editable(self, flairs):
        post = self.make_post(corporation=None, content="Legacy<br>ad")
        form = self.form(
            instance=post, content="Legacy<br>ad", posting_day="friday"
        )
        self.assertTrue(form.is_valid(), form.errors)
