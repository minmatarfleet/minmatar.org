from django.test import Client
from django.contrib.auth.models import Permission
from django.db.models import signals

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from esi.models import Token
from posts.authors import MINMATAR_FLEET_AUTHOR_NAME
from posts.models import EvePost, EveTag

BASE_URL = "/api/blog"


class PostsRouterTestCase(TestCase):
    """Test cases for the blog posts router."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

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

    def test_filter_posts_by_tag(self):
        propaganda = EveTag.objects.create(tag="Propaganda")
        frontlines = EveTag.objects.create(tag="Frontlines")

        propaganda_post = EvePost.objects.create(
            title="Propaganda post",
            state="published",
            seo_description="Propaganda",
            slug="propaganda-post",
            content="Propaganda body",
            user=self.user,
        )
        propaganda_post.tags.add(propaganda)

        other_post = EvePost.objects.create(
            title="Frontlines post",
            state="published",
            seo_description="Frontlines",
            slug="frontlines-post",
            content="Frontlines body",
            user=self.user,
        )
        other_post.tags.add(frontlines)

        response = self.client.get(
            f"{BASE_URL}/posts",
            {"tag_id": propaganda.id, "status": "published"},
        )
        self.assertEqual(200, response.status_code)
        posts = response.json()
        self.assertEqual(1, len(posts))
        self.assertEqual("Propaganda post", posts[0]["title"])

    def test_list_posts_includes_author_primary_character(self):
        token = Token.objects.create(character_id=634915984, user=self.user)
        character = EveCharacter.objects.create(
            character_id=634915984,
            character_name="BearThatCares",
            token=token,
            user=self.user,
        )
        set_primary_character(self.user, character)

        post = EvePost.objects.create(
            title="Authored post",
            state="published",
            seo_description="Testing author",
            slug="authored-post",
            content="Body",
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/posts", {"status": "published"}
        )
        self.assertEqual(200, response.status_code)
        posts = response.json()
        self.assertEqual(1, len(posts))
        self.assertEqual(post.id, posts[0]["post_id"])
        self.assertEqual(634915984, posts[0]["author_character_id"])
        self.assertEqual("BearThatCares", posts[0]["author_character_name"])

    def test_list_posts_without_primary_character_uses_fleet_fallback(self):
        post = EvePost.objects.create(
            title="Fleet post",
            state="published",
            seo_description="Testing author fallback",
            slug="fleet-post",
            content="Body",
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/posts", {"status": "published"}
        )
        self.assertEqual(200, response.status_code)
        posts = response.json()
        matching = [item for item in posts if item["post_id"] == post.id]
        self.assertEqual(1, len(matching))
        self.assertEqual(0, matching[0]["author_character_id"])
        self.assertEqual(
            MINMATAR_FLEET_AUTHOR_NAME, matching[0]["author_character_name"]
        )
