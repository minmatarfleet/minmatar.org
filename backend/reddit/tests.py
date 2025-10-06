from unittest.mock import patch

from app.test import TestCase

from reddit.service import RedditService
from reddit.models import RedditScheduledPost


class RedditServiceTestCase(TestCase):
    """Unit tests for the Reddit service"""

    @patch("reddit.service.client")
    def test_mocked_reddit_post(self, client):
        client.submit_post.return_value = {}

        rsp = RedditScheduledPost.objects.create(
            title="Test 1 - {ID}",
            content="Testing",
        )

        title = RedditService().post_recriutment_ad(rsp)

        self.assertEqual(20, len(title))
