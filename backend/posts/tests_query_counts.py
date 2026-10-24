"""The posts list must not look up each author's main one query at a time."""

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from posts.models import EvePost

BASE_URL = "/api/blog"


class PostsListQueryCountTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.posts = 0

    def add_posts(self, count: int):
        for _ in range(count):
            i = self.posts
            self.posts += 1
            user = User.objects.create_user(username=f"author{i}")
            char = EveCharacter.objects.create(
                character_id=60000 + i, character_name=f"Author {i}", user=user
            )
            set_primary_character(user, char)
            EvePost.objects.create(
                title=f"Post {i}",
                seo_description="d",
                slug=f"post-{i}",
                content="body",
                user=user,
                state="published",
            )

    def count_queries(self) -> tuple[int, list]:
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(f"{BASE_URL}/posts")
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries), response.json()

    def test_posts_list_queries_do_not_grow_with_authors(self):
        self.add_posts(2)
        few, body = self.count_queries()
        self.assertEqual(len(body), 2)
        self.add_posts(4)
        many, body = self.count_queries()
        self.assertEqual(len(body), 6)
        self.assertEqual(few, many)
        self.assertEqual(
            sorted(row["author_character_name"] for row in body),
            [f"Author {i}" for i in range(6)],
        )
