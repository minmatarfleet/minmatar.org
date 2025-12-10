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

    def test_gallery_endpoint_basic(self):
        """Test basic gallery endpoint functionality."""
        # Create a post with images
        data = {
            "title": "Gallery Test Post",
            "state": "published",
            "seo_description": "Testing gallery",
            "content": "Check out these images: ![Image 1](https://example.com/image1.jpg) and ![Image 2](https://example.com/image2.png)",
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

        # Test gallery endpoint
        response = self.client.get(f"{BASE_URL}/gallery")
        self.assertEqual(200, response.status_code)

        gallery_data = response.json()
        self.assertIn("images", gallery_data)
        self.assertIn("next_cursor", gallery_data)
        self.assertIn("has_more", gallery_data)

        # Should have 2 images from the post
        self.assertEqual(2, len(gallery_data["images"]))

        # Check image data structure
        image = gallery_data["images"][0]
        self.assertIn("image_url", image)
        self.assertIn("post_id", image)
        self.assertIn("post_title", image)
        self.assertIn("cursor_id", image)
        self.assertEqual("https://example.com/image1.jpg", image["image_url"])
        self.assertEqual("Gallery Test Post", image["post_title"])

    def test_gallery_endpoint_filtering(self):
        """Test gallery endpoint with filters."""
        # Test with status filter
        response = self.client.get(f"{BASE_URL}/gallery?status=draft")
        self.assertEqual(200, response.status_code)

        # Test with limit
        response = self.client.get(f"{BASE_URL}/gallery?limit=10")
        self.assertEqual(200, response.status_code)

        # Test with include_metadata=false
        response = self.client.get(f"{BASE_URL}/gallery?include_metadata=false")
        self.assertEqual(200, response.status_code)
        gallery_data = response.json()
        if gallery_data["images"]:
            image = gallery_data["images"][0]
            self.assertEqual("", image["post_title"])  # Should be empty when metadata disabled
