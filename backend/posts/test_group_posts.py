"""Tribe group posts: visibility, publishing rights, announcement."""

from unittest.mock import patch

from django.test import Client

from app.test import TestCase
from app.testing import make_token
from posts.models import EvePost
from tribes.models import TribeGroup
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    ROLE_ID,
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/blog"


class GroupPostTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group()
        self.other_group = make_tribe_group(
            "Carriers", "capitals.carriers", role_id=None
        )
        self.author = make_user("author")
        add_member(self.group, self.author)
        self.member = make_user("member")
        add_member(self.group, self.member)
        self.chief = make_user("chief")
        self.group.chief = self.chief
        self.group.save()
        self.outsider = make_user("outsider", perms=("add_evepost",))

    def call(self, method, path, user=None, data=None):
        kwargs = {}
        if user is not None:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {make_token(user)}"
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(f"{BASE_URL}{path}", **kwargs)

    def post(self, title, **fields):
        values = {
            "title": title,
            "state": "published",
            "seo_description": "",
            "slug": EvePost.generate_slug(title),
            "content": "Body",
            "user": self.author,
        }
        values.update(fields)
        return EvePost.objects.create(**values)

    def listed(self, user=None, query=""):
        response = self.call("get", f"/posts{query}", user)
        self.assertEqual(response.status_code, 200, response.content)
        return {row["post_id"] for row in response.json()}

    def payload(self, **fields):
        data = {
            "title": "Dread doctrine update",
            "state": "published",
            "seo_description": "New fits",
            "content": "Fits",
            "tag_ids": [],
            "host_group_id": self.group.id,
        }
        data.update(fields)
        return data

    def test_members_only_post_hidden_in_list_and_detail(self):
        public = self.post("Public")
        group_public = self.post("Group public", host_group=self.group)
        hidden = self.post("Hidden", host_group=self.group, members_only=True)

        self.assertEqual(self.listed(), {public.id, group_public.id})
        self.assertEqual(
            self.listed(self.outsider), {public.id, group_public.id}
        )
        for user in (self.member, self.chief, self.author):
            self.assertIn(hidden.id, self.listed(user))

        response = self.call("get", f"/posts/{hidden.id}")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "members_only")
        self.assertEqual(response.json()["host_group"]["name"], "Dreads")
        self.assertNotIn("Body", response.content.decode())
        self.assertEqual(
            self.call("get", f"/posts/{hidden.id}", self.outsider).status_code,
            403,
        )
        response = self.call("get", f"/posts/{hidden.id}", self.member)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["members_only"])
        self.assertEqual(response.json()["host_group"]["id"], self.group.id)

        response = self.call("get", f"/posts/{public.id}")
        self.assertIsNone(response.json()["host_group"])
        self.assertFalse(response.json()["members_only"])

    def test_tribe_group_filter_includes_hosted_and_tagged(self):
        hosted = self.post("Hosted", host_group=self.group)
        tagged = self.post("Tagged")
        tagged.tribe_groups.add(self.group)
        self.post("Elsewhere", host_group=self.other_group)
        self.assertEqual(
            self.listed(query=f"?tribe_group_id={self.group.id}"),
            {hosted.id, tagged.id},
        )

    @patch("posts.announce.queue_channel_message")
    def test_create_needs_post_right(self, queue):
        response = self.call("post", "/posts", self.member, self.payload())
        self.assertEqual(response.status_code, 403)
        # posts.create alone doesn't let you post as a group.
        response = self.call("post", "/posts", self.outsider, self.payload())
        self.assertEqual(response.status_code, 403)

        self.group.post_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        response = self.call(
            "post", "/posts", self.member, self.payload(members_only=True)
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["members_only"])
        queue.assert_not_called()

    @patch("posts.announce.queue_channel_message")
    def test_group_without_alliance_posts_stores_members_only(self, queue):
        self.group.allow_alliance_posts = False
        self.group.save()
        response = self.call("post", "/posts", self.chief, self.payload())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(EvePost.objects.get().members_only)

    @patch("posts.announce.queue_channel_message")
    def test_announce_once_on_first_publish(self, queue):
        response = self.call(
            "post",
            "/posts",
            self.chief,
            self.payload(state="draft", announce=True),
        )
        self.assertEqual(response.status_code, 200, response.content)
        post_id = response.json()["post_id"]
        queue.assert_not_called()

        self.call(
            "patch",
            f"/posts/{post_id}",
            self.chief,
            {"state": "published", "announce": True},
        )
        queue.assert_called_once()
        channel_id = queue.call_args[0][0]
        message = queue.call_args[1]["message"]
        self.assertEqual(channel_id, GROUP_CHANNEL_ID)
        self.assertTrue(message.startswith(f"<@&{ROLE_ID}> "))
        self.assertIn("**Dread doctrine update**", message)
        self.assertIn(
            f"/alliance/propaganda/dread-doctrine-update-{post_id}", message
        )
        self.assertIsNotNone(EvePost.objects.get(id=post_id).announced_at)

        self.call(
            "patch",
            f"/posts/{post_id}",
            self.chief,
            {"content": "Edited", "announce": True},
        )
        queue.assert_called_once()

    def test_edit_rights(self):
        post = self.post("Group post", host_group=self.group)
        # The author without posts.edit, and the group's chief, may edit.
        response = self.call(
            "patch", f"/posts/{post.id}", self.author, {"content": "A"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.call(
            "patch", f"/posts/{post.id}", self.chief, {"content": "B"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.call(
            "patch", f"/posts/{post.id}", self.member, {"content": "C"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.call("delete", f"/posts/{post.id}", self.member).status_code,
            403,
        )
        self.assertEqual(
            self.call("delete", f"/posts/{post.id}", self.chief).status_code,
            204,
        )

    def test_patch_without_flags_keeps_members_only(self):
        post = self.post("Hidden", host_group=self.group, members_only=True)
        self.call("patch", f"/posts/{post.id}", self.author, {"content": "X"})
        post.refresh_from_db()
        self.assertTrue(post.members_only)
