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
        self.assertEqual(
            rsp.last_reddit_post_url, client.submit_post.return_value["url"]
        )
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

    @patch("reddit.client.requests.post")
    @patch.object(RedditClient, "get_access_token")
    def test_submit_post_parses_legacy_jquery_response(
        self, get_token, requests_post
    ):
        """submit_post returns url/id when Reddit returns legacy jQuery payload."""
        get_token.return_value = "fake-token"
        requests_post.return_value.status_code = 200
        requests_post.return_value.json.return_value = {
            "success": True,
            "jquery": [
                [1, 10, "attr", "redirect"],
                [
                    10,
                    11,
                    "call",
                    [
                        "https://www.reddit.com/r/MinmatarFleet/comments/1qs4fx2/test/"
                    ],
                ],
            ],
        }

        result = RedditClient().submit_post(
            subreddit="MinmatarFleet",
            title="test",
            content="body",
        )

        self.assertEqual(
            result,
            {
                "url": "https://www.reddit.com/r/MinmatarFleet/comments/1qs4fx2/test/",
                "id": "1qs4fx2",
            },
        )

    @patch("reddit.client.requests.post")
    @patch.object(RedditClient, "get_access_token")
    def test_submit_post_returns_none_when_no_token(
        self, get_token, requests_post
    ):
        get_token.return_value = None
        result = RedditClient().submit_post("foo", "title", "content")
        self.assertIsNone(result)
        requests_post.assert_not_called()
