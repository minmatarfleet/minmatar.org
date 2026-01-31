from unittest.mock import patch

from app.test import TestCase

from reddit.client import RedditClient
from reddit.service import RedditService
from reddit.models import RedditScheduledPost


class RedditServiceTestCase(TestCase):
    """Unit tests for the Reddit service"""

    @patch("reddit.service.client")
    def test_mocked_reddit_post(self, client):
        client.submit_post.return_value = {
            "url": "https://www.reddit.com/r/foo/comments/abc123/test/",
            "id": "abc123",
        }

        rsp = RedditScheduledPost.objects.create(
            title="Test 1 - {ID}",
            content="Testing",
            subreddit="foo",
            posting_day="monday",
        )

        title = RedditService().post_recriutment_ad(rsp)

        self.assertEqual(20, len(title))
        rsp.refresh_from_db()
        self.assertEqual(rsp.last_reddit_post_url, client.submit_post.return_value["url"])
        self.assertEqual(rsp.last_reddit_post_title, title)
        self.assertIsNotNone(rsp.last_post_at)

    @patch("reddit.service.client")
    def test_mocked_reddit_post_no_url_when_submit_fails(self, client):
        client.submit_post.return_value = None

        rsp = RedditScheduledPost.objects.create(
            title="Test 2 - {ID}",
            content="Testing",
            subreddit="foo",
            posting_day="monday",
        )

        RedditService().post_recriutment_ad(rsp)

        rsp.refresh_from_db()
        self.assertIsNone(rsp.last_reddit_post_url)
        self.assertIsNone(rsp.last_reddit_post_title)
        self.assertIsNotNone(rsp.last_post_at)


class RedditClientTestCase(TestCase):
    """Unit tests for the Reddit client"""

    def test_parse_redirect_from_jquery_finds_redirect_url(self):
        jquery = [
            [1, 10, "attr", "redirect"],
            [10, 11, "call", ["https://www.reddit.com/r/MinmatarFleet/comments/1qs4fx2/test/"]],
        ]
        url = RedditClient._parse_redirect_from_jquery(jquery)
        self.assertEqual(
            url,
            "https://www.reddit.com/r/MinmatarFleet/comments/1qs4fx2/test/",
        )

    def test_parse_redirect_from_jquery_returns_none_when_no_redirect(self):
        jquery = [[0, 1, "call", ["body"]], [1, 2, "attr", "find"]]
        self.assertIsNone(RedditClient._parse_redirect_from_jquery(jquery))

    def test_parse_redirect_from_jquery_returns_none_when_empty(self):
        self.assertIsNone(RedditClient._parse_redirect_from_jquery([]))
