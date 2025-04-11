from django.test import Client
from django.contrib.auth.models import Permission

from app.test import TestCase

BASE_URL = "/api/blog"


class PostsRouterTestCase(TestCase):
    """Test cases for the blog posts router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_basic_blog_post(self):
        response = self.client.get(
            f"{BASE_URL}/posts",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()))

        data = {
            "title": "Test post 1",
            "state": "draft",
            "seo_description": "Testing",
            "content": "This is a test",
            "tag_ids": [],
        }

        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evepost")
        )
        response = self.client.post(
            f"{BASE_URL}/posts",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/posts",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        posts = response.json()
        self.assertEqual(1, len(posts))
        self.assertEqual("Test post 1", posts[0]["title"])

        post_id = posts[0]["post_id"]

        response = self.client.get(
            f"{BASE_URL}/posts/{post_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        post = response.json()
        self.assertEqual("This is a test", post["content"])
