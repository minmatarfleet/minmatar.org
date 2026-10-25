from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TransactionTestCase, override_settings

from app.test import TestCase
from discord.models import DiscordChannel, DiscordGuild, DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from reddit.admin import RedditPostTemplateAdminForm
from reddit.client import RedditClient, normalize_subreddit
from reddit.markdown import check_reddit_markdown
from reddit.corporation_posts import PostSettingsError, save_post_settings
from reddit.models import RedditAccount, RedditPost, RedditPostTemplate
from reddit.oauth import RedditOAuthError
from reddit import schedule
from reddit.scheduling import (
    ACCOUNT_INVALID,
    DISCORD_MESSAGE_LIMIT,
    NO_ACCOUNT,
    NOT_APPROVED,
    POST_FAILED,
    claim,
    deliver,
    reminder_messages,
    submit,
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
        }
        values.update(fields)
        return RedditPostTemplate.objects.create(**values)

    def confirmed_slot(self, template, when=THURSDAY_1800, **fields):
        values = {
            "template": template,
            "slot_date": when.date(),
            "scheduled_for": when,
            "status": RedditPost.CONFIRMED,
        }
        values.update(fields)
        return RedditPost.objects.create(**values)

    def claimed(self, template):
        post = self.confirmed_slot(template)
        self.assertTrue(claim(post))
        post.refresh_from_db()
        return post

    def other_corporation(self):
        return EveCorporation.objects.create(
            corporation_id=98000009, name="Other Corp"
        )

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


class DeliveryTestCase(CorporationPostTestCase):
    """Confirmed slots go out once, when due."""

    def test_a_slot_can_only_be_claimed_once(self):
        post = self.confirmed_slot(self.make_post())
        self.assertTrue(claim(post))
        self.assertFalse(claim(post))
        post.refresh_from_db()
        self.assertEqual(RedditPost.PENDING, post.status)

    def test_drafts_are_never_claimed(self):
        post = self.confirmed_slot(self.make_post(), status=RedditPost.DRAFT)
        self.assertFalse(claim(post))

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_each_slot_is_delivered_once(self, deliver_mock):
        self.confirmed_slot(self.make_post())
        self.assertEqual(["reminded"], schedule.deliver_due(THURSDAY_1800))
        self.assertEqual(
            [], schedule.deliver_due(THURSDAY_1800 + timedelta(minutes=15))
        )
        self.assertEqual(1, deliver_mock.call_count)

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_not_delivered_before_its_time(self, deliver_mock):
        self.confirmed_slot(self.make_post())
        schedule.deliver_due(THURSDAY_1800 - timedelta(minutes=1))
        deliver_mock.assert_not_called()

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_slot_missed_by_more_than_the_catch_up_window_is_skipped(
        self, deliver_mock
    ):
        post = self.confirmed_slot(self.make_post())
        schedule.deliver_due(THURSDAY_1800 + timedelta(hours=13))
        deliver_mock.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(RedditPost.SKIPPED, post.status)
        self.assertEqual("missed", post.fallback_reason)

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_paused_post_is_skipped(self, deliver_mock):
        post = self.confirmed_slot(self.make_post(paused=True))
        schedule.deliver_due(THURSDAY_1800)
        deliver_mock.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(RedditPost.SKIPPED, post.status)


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
        template = self.make_post(delivery_method="discord_reminder")
        post = self.claimed(template)
        self.assertEqual("reminded", deliver(template, post))
        submit_post.assert_not_called()
        (dm_user,) = {c.args[0] for c in discord().send_dm.call_args_list}
        self.assertEqual("4242", dm_user)
        post.refresh_from_db()
        self.assertEqual(RedditPost.REMINDED, post.status)
        self.assertEqual("", post.fallback_reason)

    @patch("reddit.scheduling.RedditClient")
    def test_automatic_posts_as_the_ceo_account(
        self, client_class, submit_post, discord
    ):
        client_class.return_value.submit_post.return_value = SUBMITTED
        account = self.link_reddit()
        template = self.make_post(delivery_method="automatic", approved=True)
        post = self.claimed(template)
        self.assertEqual("posted", deliver(template, post, THURSDAY_1800))
        client_class.assert_called_once_with(account)
        discord().send_dm.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(RedditPost.POSTED, post.status)
        self.assertEqual(SUBMITTED["url"], post.reddit_url)
        self.assertEqual("Join the Rat", post.title)
        self.assertEqual(THURSDAY_1800, post.delivered_at)

    @patch("reddit.scheduling.RedditClient")
    def test_alliance_method_posts_as_the_alliance_account(
        self, client_class, submit_post, discord
    ):
        client_class.return_value.submit_post.return_value = SUBMITTED
        # Even with the CEO's account linked, it goes out as the alliance.
        self.link_reddit()
        template = self.make_post(approved=True)
        self.assertEqual("alliance", template.delivery_method)
        post = self.claimed(template)
        self.assertEqual("posted", deliver(template, post, THURSDAY_1800))
        client_class.assert_called_once_with()
        discord().send_dm.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(SUBMITTED["url"], post.reddit_url)

    def test_alliance_method_needs_no_linked_account(
        self, submit_post, discord
    ):
        template = self.make_post(approved=True)
        post = self.claimed(template)
        self.assertEqual("posted", deliver(template, post))
        submit_post.assert_called_once()

    def _reminder_reason(self, template, discord):
        post = self.claimed(template)
        with patch(
            "reddit.scheduling.reminder_messages", return_value=["hi"]
        ) as messages:
            self.assertEqual("reminded", deliver(template, post))
        reason = messages.call_args.args[1]
        post.refresh_from_db()
        self.assertEqual(reason, post.fallback_reason)
        return reason

    def test_unapproved_automatic_post_falls_back_to_reminder(
        self, submit_post, discord
    ):
        self.link_reddit()
        post = self.make_post(delivery_method="automatic", approved=False)
        self.assertEqual(NOT_APPROVED, self._reminder_reason(post, discord))
        submit_post.assert_not_called()

    def test_unapproved_alliance_post_falls_back_to_reminder(
        self, submit_post, discord
    ):
        post = self.make_post(approved=False)
        self.assertEqual(NOT_APPROVED, self._reminder_reason(post, discord))
        submit_post.assert_not_called()

    def test_failed_alliance_post_reminds(self, submit_post, discord):
        submit_post.return_value = None
        post = self.make_post(approved=True)
        self.assertEqual(POST_FAILED, self._reminder_reason(post, discord))

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


class NoDiscordTestCase(CorporationPostTestCase):
    @patch("reddit.scheduling.DiscordClient")
    def test_ceo_without_discord_is_skipped(self, discord):
        template = self.make_post()
        post = self.claimed(template)
        self.assertEqual("skipped", deliver(template, post))
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
            "**SWITCH TO MARKDOWN MODE IN THE EDITOR FIRST**\n**Title**",
            messages[0],
        )
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
        self.assertEqual("evejobs", post.subreddit)
        self.assertTrue(post.in_rotation)
        self.assertFalse(post.approved)

    def test_saving_puts_the_post_in_the_draft(self):
        post = save_post_settings(
            self.corporation, "Title", "Body", "discord_reminder"
        )
        self.assertTrue(post.posts.filter(status=RedditPost.DRAFT).exists())

    def test_ceo_pauses_and_resumes(self):
        post = save_post_settings(
            self.corporation, "Title", "Body", "discord_reminder", True
        )
        self.assertFalse(post.in_rotation)
        self.assertFalse(post.posts.exists())
        post = save_post_settings(
            self.corporation, "Title", "Body", "discord_reminder"
        )
        self.assertTrue(post.paused)
        post = save_post_settings(
            self.corporation, "Title", "Body", "discord_reminder", False
        )
        self.assertTrue(post.in_rotation)
        self.assertTrue(post.posts.exists())

    def test_editing_an_approved_post_waits_for_review(self):
        post = self.make_post(approved=True, approved_by=self.user)
        save_post_settings(
            self.corporation, "New title", post.content, "automatic"
        )
        post.refresh_from_db()
        self.assertTrue(post.approved)
        self.assertEqual("Join the Rat", post.title)
        self.assertEqual("New title", post.change_requests.get().title)

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
        template = self.make_post(approved=True)
        RedditPost.objects.create(
            template=template,
            status=RedditPost.POSTED,
            reddit_url=SUBMITTED["url"],
            delivered_at=THURSDAY_1800 - timedelta(days=7),
        )
        RedditPost.objects.create(
            template=template,
            status=RedditPost.REMINDED,
            delivered_at=THURSDAY_1800,
        )
        self.link_reddit()
        body = self.client.get(self.url, **self.auth()).json()
        self.assertEqual(SUBMITTED["url"], body["last_reddit_post_url"])
        self.assertTrue(body["last_post_at"].startswith("2026-10-08"))
        self.assertTrue(body["last_reminder_at"].startswith("2026-10-15"))
        self.assertTrue(body["exists"])
        self.assertEqual("active", body["rotation_status"])
        self.assertEqual("normal", body["priority"])
        self.assertFalse(body["paused"])
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
        self.assertFalse(RedditPostTemplate.objects.exists())

    def test_director_edits_but_sees_the_ceos_account(self):
        self.make_post(approved=True)
        self.link_reddit()
        token = self.other_user_token()
        director_user = User.objects.get(username="not-ceo")
        self.corporation.directors.add(
            EveCharacter.objects.create(
                character_id=91000002,
                character_name="Rat Director",
                user=director_user,
            )
        )
        body = self.client.get(self.url, **self.auth(token)).json()
        self.assertEqual("BearThatCares", body["reddit_account"]["username"])
        self.assertFalse(body["can_link_account"])
        self.assertTrue(
            self.client.get(self.url, **self.auth()).json()["can_link_account"]
        )
        response = self.client.put(
            self.url,
            data={
                "title": "Join the Rat",
                "content": "We fly together. Ask for a director.",
                "delivery_method": "automatic",
            },
            content_type="application/json",
            **self.auth(token),
        )
        self.assertEqual(200, response.status_code)

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
        body = response.json()
        self.assertEqual("active", body["rotation_status"])
        self.assertEqual("evejobs", body["subreddit"])
        self.assertTrue(body["upcoming"])
        self.assertFalse(body["upcoming"][0]["confirmed"])
        self.assertEqual(2 * 1, body["interval_days"])
        post = RedditPostTemplate.objects.get(corporation=self.corporation)
        self.assertEqual("# Rattini\nWe fly.", post.content)

    def test_settings_before_the_first_save(self):
        body = self.client.get(self.url, **self.auth()).json()
        self.assertFalse(body["exists"])
        self.assertEqual("evejobs", body["subreddit"])
        self.assertEqual("not_set_up", body["rotation_status"])
        self.assertEqual([], body["upcoming"])
        self.assertEqual("alliance", body["delivery_method"])

    def test_ceo_pauses_the_post(self):
        self.make_post()
        response = self.client.put(
            self.url,
            data={
                "title": "Title",
                "content": "Body",
                "delivery_method": "discord_reminder",
                "paused": True,
            },
            content_type="application/json",
            **self.auth(),
        )
        body = response.json()
        self.assertEqual("paused", body["rotation_status"])
        self.assertEqual([], body["upcoming"])
        self.assertIsNone(body["interval_days"])

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
        self.assertFalse(RedditPostTemplate.objects.exists())

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
            "corporation": self.corporation.pk,
            "subreddit": "evejobs",
            "title": "Title",
            "content": "Fine",
            "priority": "normal",
            "posting_window": "any",
            "delivery_method": "automatic",
        }
        values.update(data)
        return RedditPostTemplateAdminForm(data=values, instance=instance)

    def test_admin_rejects_new_unrenderable_content(self):
        form = self.form(content="<center>hi</center>")
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)

    @patch("reddit.admin.reddit_client.get_link_flairs", return_value=[])
    def test_admin_keeps_existing_content_editable(self, flairs):
        post = self.make_post(content="Legacy<br>ad")
        form = self.form(
            instance=post, content="Legacy<br>ad", priority="high"
        )
        self.assertTrue(form.is_valid(), form.errors)


@patch("reddit.scheduling.DiscordClient")
class DiscordChannelTestCase(CorporationPostTestCase):
    def setUp(self):
        super().setUp()
        guild = DiscordGuild.objects.create(guild_id=424242, name="Test guild")
        self.channel = DiscordChannel.objects.create(
            channel_id=555,
            guild=guild,
            name="recruitment",
            channel_type=DiscordChannel.TEXT,
        )

    @patch.object(RedditClient, "submit_post", return_value=SUBMITTED)
    def test_reddit_post_is_linked_in_the_channel(self, submit_post, discord):
        template = self.make_post(discord_channel=self.channel)
        submit(template)
        discord().create_message.assert_called_once_with(
            555, f"**New Reddit post:** Join the Rat\n{SUBMITTED['url']}"
        )

    def test_admin_only_offers_text_channels(self, discord):
        DiscordChannel.objects.create(
            channel_id=556,
            guild=self.channel.guild,
            name="Fleet comms",
            channel_type=DiscordChannel.VOICE,
        )
        form = AdminMarkdownTestCase.form(self)
        self.assertEqual(
            [self.channel],
            list(form.fields["discord_channel"].queryset),
        )


class PostTemplateMigrationTestCase(TransactionTestCase):
    """0009/0010 turn the old last_* fields into RedditPost rows."""

    before = [("reddit", "0008_reminder_only_and_drop_alliance_posts")]
    after = [("reddit", "0010_drop_last_fields")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        with patch("builtins.print"):
            executor.migrate(executor.loader.graph.leaf_nodes())

    def test_history_and_channel_are_carried_over(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        corporation = old.get_model("eveonline", "EveCorporation").objects
        corporation = corporation.create(corporation_id=98000050, name="Old")
        guild = old.get_model("discord", "DiscordGuild").objects.create(
            guild_id=424242, name="Test guild"
        )
        old.get_model("discord", "DiscordChannel").objects.create(
            channel_id=777, guild=guild, name="recruiting", channel_type="text"
        )
        posts = old.get_model("reddit", "RedditScheduledPost").objects
        slot = datetime(2026, 10, 15, 17, 0, tzinfo=dt_timezone.utc)
        posts.create(
            corporation=corporation,
            subreddit="evejobs",
            title="Join",
            content="Body",
            posting_day="thursday",
            posting_time=time(17, 0),
            discord_channel_id=777,
            last_scheduled_on=slot.date(),
            last_reminder_at=slot + timedelta(minutes=2),
            last_post_at=slot - timedelta(days=3),
            last_reddit_post_url=SUBMITTED["url"],
            last_reddit_post_title="Join",
        )
        posts.create(title="Alliance", content="Body", subreddit="evejobs")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        with patch("builtins.print"):
            executor.migrate(self.after)
        new = executor.loader.project_state(self.after).apps

        (template,) = new.get_model(
            "reddit", "RedditPostTemplate"
        ).objects.all()
        self.assertEqual(777, template.discord_channel.channel_id)
        rows = {
            (row.scheduled_for, row.status, row.reddit_url)
            for row in template.posts.all()
        }
        self.assertEqual(
            {
                (slot, "reminded", ""),
                (None, "posted", SUBMITTED["url"]),
            },
            rows,
        )


class RestoreCorporationPostsTestCase(TransactionTestCase):
    """0011 puts back the corporation posts 0008 deleted; 0012 then puts
    them in the rotation."""

    before = [("reddit", "0010_drop_last_fields")]
    after = [("reddit", "0012_rotation")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        with patch("builtins.print"):
            executor.migrate(executor.loader.graph.leaf_nodes())

    def migrate(self, corporation_ids, existing_title=None):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        corporations = old.get_model("eveonline", "EveCorporation").objects
        for corporation_id in corporation_ids:
            corporation = corporations.create(
                corporation_id=corporation_id, name=f"Corp {corporation_id}"
            )
            if existing_title:
                old.get_model("reddit", "RedditPostTemplate").objects.create(
                    corporation=corporation,
                    title=existing_title,
                    content="Body",
                )
        old.get_model("discord", "DiscordGuild").objects.get_or_create(
            guild_id=1041384161505722368, defaults={"name": "Minmatar Fleet"}
        )
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        with patch("builtins.print") as printed:
            executor.migrate(self.after)
        return " ".join(str(c.args[0]) for c in printed.call_args_list)

    def test_restores_posts_into_the_rotation(self):
        output = self.migrate([98726134, 98741376])
        templates = {
            t.corporation.corporation_id: t
            for t in RedditPostTemplate.objects.select_related(
                "corporation", "discord_channel"
            )
        }
        rats = templates[98726134]
        self.assertEqual("rats", rats.discord_channel.name)
        self.assertEqual(1267941181732556902, rats.discord_channel.channel_id)
        self.assertTrue(rats.title.startswith("Rattini Tribe"))
        self.assertEqual("evejobs", rats.subreddit)
        self.assertEqual("discord_reminder", rats.delivery_method)
        self.assertTrue(rats.approved)
        self.assertTrue(rats.in_rotation)
        self.assertEqual("normal", rats.priority)
        (post,) = rats.posts.all()
        self.assertEqual(RedditPost.POSTED, post.status)
        self.assertIn("reddit.com", post.reddit_url)
        self.assertEqual(post.created_at, post.delivered_at)
        self.assertEqual("high", templates[98741376].priority)
        self.assertIn("Not restoring The Dark Tribe", output)
        self.assertNotIn("FL33T", output)

    def test_keeps_a_post_the_ceo_already_made_paused(self):
        self.migrate([98726134], existing_title="Written since the deploy")
        (template,) = RedditPostTemplate.objects.all()
        self.assertEqual("Written since the deploy", template.title)
        # It never had a day, so it waits for the CEO to resume it.
        self.assertTrue(template.paused)


class AllianceAccountMigrationTestCase(TransactionTestCase):
    """0013 moves the reminder-only posts to the alliance account."""

    before = [("reddit", "0012_rotation")]
    after = [("reddit", "0013_alliance_account_default")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        with patch("builtins.print"):
            executor.migrate(executor.loader.graph.leaf_nodes())

    def test_reminders_move_to_the_alliance_account(self):
        executor = MigrationExecutor(connection)
        with patch("builtins.print"):
            executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        corporations = old.get_model("eveonline", "EveCorporation").objects
        templates = old.get_model("reddit", "RedditPostTemplate").objects
        for corporation_id, method in (
            (1, "discord_reminder"),
            (2, "automatic"),
        ):
            templates.create(
                corporation=corporations.create(
                    corporation_id=corporation_id, name=f"Corp {method}"
                ),
                title="Title",
                content="Body",
                delivery_method=method,
            )
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        with patch("builtins.print"):
            executor.migrate(self.after)
        self.assertEqual(
            {1: "alliance", 2: "automatic"},
            dict(
                RedditPostTemplate.objects.values_list(
                    "corporation__corporation_id", "delivery_method"
                )
            ),
        )
