from unittest.mock import patch

from app.test import TestCase
from eveonline.models import EveCorporation

from reddit.client import RedditClient
from reddit.models import RedditPost, RedditPostTemplate
from reddit.service import RedditService


class RedditServiceTestCase(TestCase):
    """Unit tests for the Reddit service"""

    def make_template(self, title):
        corporation = EveCorporation.objects.create(
            corporation_id=98000100, name="Service Corp"
        )
        return RedditPostTemplate.objects.create(
            corporation=corporation,
            title=title,
            content="Testing",
            subreddit="foo",
        )

    @patch("reddit.scheduling.RedditClient")
    def test_mocked_reddit_post(self, client_class):
        client = client_class.return_value
        client.submit_post.return_value = {
            "url": "https://www.reddit.com/r/foo/comments/abc123/test/",
            "id": "abc123",
        }
        template = self.make_template("Test 1 - {ID}")

        post = RedditService().post_recriutment_ad(template)

        # No CEO account linked, so it goes out as the alliance.
        client_class.assert_called_once_with()
        post.refresh_from_db()
        self.assertEqual(20, len(post.title))
        self.assertEqual(RedditPost.POSTED, post.status)
        self.assertIsNone(post.scheduled_for)
        self.assertIsNotNone(post.delivered_at)
        self.assertEqual(
            post.reddit_url, client.submit_post.return_value["url"]
        )

    @patch("reddit.scheduling.RedditClient")
    def test_mocked_reddit_post_no_url_when_submit_fails(self, client_class):
        client_class.return_value.submit_post.return_value = None
        template = self.make_template("Test 2 - {ID}")

        post = RedditService().post_recriutment_ad(template)

        post.refresh_from_db()
        self.assertEqual(RedditPost.FAILED, post.status)
        self.assertEqual("", post.reddit_url)


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
