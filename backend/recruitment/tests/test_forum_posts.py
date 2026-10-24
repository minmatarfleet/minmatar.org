from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCharacter, EveCorporation
from recruitment.forum_posts import ForumPostError, save_forum_post
from recruitment.forums import TopicNotFound
from recruitment.models import ForumRecruitmentPost

THREAD = "https://forums.eveonline.com/t/rattini-tribe-is-recruiting/496493"
TOPIC = {
    "id": 496493,
    "slug": "rattini-tribe-is-recruiting",
    "title": "Rattini Tribe is recruiting",
    "category_id": 63,
}


class ForumPostTestCase(TestCase):
    """A corporation whose CEO is self.user; the forum is always mocked."""

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
        fetch = patch(
            "recruitment.forum_posts.fetch_topic", return_value=dict(TOPIC)
        )
        self.fetch_topic = fetch.start()
        self.addCleanup(fetch.stop)


class SaveForumPostTestCase(ForumPostTestCase):
    def test_links_thread_with_forum_title(self):
        post = save_forum_post(self.corporation, THREAD + "/4?u=x", self.user)
        self.assertEqual(THREAD, post.url)
        self.assertEqual(496493, post.topic_id)
        self.assertEqual("Rattini Tribe is recruiting", post.title)
        self.assertEqual(self.user, post.linked_by)
        self.fetch_topic.assert_called_once_with(496493)

    def test_uses_the_forum_slug(self):
        stale = "https://forums.eveonline.com/t/old-title/496493"
        post = save_forum_post(self.corporation, stale, self.user)
        self.assertEqual(THREAD, post.url)

    def test_saves_without_title_when_forum_is_unreachable(self):
        self.fetch_topic.return_value = None
        post = save_forum_post(self.corporation, THREAD, self.user)
        self.assertEqual(THREAD, post.url)
        self.assertEqual("", post.title)

    def test_rejects_threads_outside_recruitment_center(self):
        self.fetch_topic.return_value = dict(TOPIC, category_id=64)
        with self.assertRaises(ForumPostError) as raised:
            save_forum_post(self.corporation, THREAD, self.user)
        self.assertEqual("not_recruitment_center", raised.exception.code)
        self.assertFalse(ForumRecruitmentPost.objects.exists())

    def test_rejects_missing_threads(self):
        self.fetch_topic.side_effect = TopicNotFound(496493)
        with self.assertRaises(ForumPostError) as raised:
            save_forum_post(self.corporation, THREAD, self.user)
        self.assertEqual("thread_not_found", raised.exception.code)

    def test_rejects_other_sites_without_fetching(self):
        with self.assertRaises(ForumPostError) as raised:
            save_forum_post(
                self.corporation, "https://evil.example/t/x/1", self.user
            )
        self.assertEqual("not_eve_forums", raised.exception.code)
        self.fetch_topic.assert_not_called()

    def test_one_thread_per_corporation(self):
        other = EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp"
        )
        ForumRecruitmentPost.objects.create(
            corporation=other, url=THREAD, topic_id=496493
        )
        with self.assertRaises(ForumPostError) as raised:
            save_forum_post(self.corporation, THREAD, self.user)
        self.assertEqual("thread_linked_elsewhere", raised.exception.code)

    def test_changing_thread_resets_bump_tracking(self):
        post = save_forum_post(self.corporation, THREAD, self.user)
        post.last_bumped_at = post.updated_at
        post.save()

        # Same thread (forum unreachable): keeps title and bump time.
        self.fetch_topic.return_value = None
        post = save_forum_post(self.corporation, THREAD + "/9", self.user)
        self.assertEqual("Rattini Tribe is recruiting", post.title)
        self.assertIsNotNone(post.last_bumped_at)

        new_thread = "https://forums.eveonline.com/t/rattini-v2/510000"
        post = save_forum_post(self.corporation, new_thread, self.user)
        self.assertEqual(new_thread, post.url)
        self.assertEqual(510000, post.topic_id)
        self.assertEqual("", post.title)
        self.assertIsNone(post.last_bumped_at)
        self.assertEqual(1, ForumRecruitmentPost.objects.count())


class RouterTestCase(ForumPostTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.url = (
            "/api/recruitment/corporations/"
            f"{self.corporation.corporation_id}/forum-post"
        )

    def auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    def other_user_token(self, **fields):
        other = User.objects.create(username="not-ceo", **fields)
        return jwt.encode(
            {"user_id": other.id}, settings.SECRET_KEY, algorithm="HS256"
        )

    def put(self, url, token=None):
        return self.client.put(
            self.url,
            data={"url": url},
            content_type="application/json",
            **self.auth(token),
        )

    def test_ceo_reads_empty_settings(self):
        response = self.client.get(self.url, **self.auth())
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["exists"])
        self.assertIsNone(body["url"])
        self.assertEqual("", body["title"])

    def test_ceo_links_thread(self):
        response = self.put(THREAD + "/7")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["exists"])
        self.assertEqual(THREAD, body["url"])
        self.assertEqual(496493, body["topic_id"])
        self.assertEqual("Rattini Tribe is recruiting", body["title"])
        self.assertEqual(
            THREAD, self.client.get(self.url, **self.auth()).json()["url"]
        )

    def test_invalid_url_is_a_400_with_code(self):
        response = self.put("https://evil.example/t/x/1")
        self.assertEqual(400, response.status_code)
        self.assertEqual("not_eve_forums", response.json()["detail"])

        self.fetch_topic.return_value = dict(TOPIC, category_id=64)
        response = self.put(THREAD)
        self.assertEqual(400, response.status_code)
        self.assertEqual("not_recruitment_center", response.json()["detail"])
        self.assertFalse(ForumRecruitmentPost.objects.exists())

    def test_empty_url_removes_link(self):
        self.put(THREAD)
        response = self.put("  ")
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["exists"])
        self.assertFalse(ForumRecruitmentPost.objects.exists())

    def test_delete_removes_link(self):
        self.put(THREAD)
        response = self.client.delete(self.url, **self.auth())
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["exists"])
        self.assertFalse(ForumRecruitmentPost.objects.exists())

    def test_only_the_ceo_can_read_or_edit(self):
        self.put(THREAD)
        other = self.other_user_token(is_superuser=True)
        self.assertEqual(
            403, self.client.get(self.url, **self.auth(other)).status_code
        )
        self.assertEqual(403, self.put("", token=other).status_code)
        self.assertEqual(
            403, self.client.delete(self.url, **self.auth(other)).status_code
        )
        self.assertTrue(ForumRecruitmentPost.objects.exists())

    def test_requires_login(self):
        self.assertEqual(401, self.client.get(self.url).status_code)

    def test_unknown_corporation_is_a_404(self):
        response = self.client.get(
            "/api/recruitment/corporations/1/forum-post", **self.auth()
        )
        self.assertEqual(404, response.status_code)
