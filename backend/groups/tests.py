from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from discord.models import DiscordRole
from eveonline.models import EveCharacter
from groups.models import GroupRequest, RequestableGroup

BASE_URL = "/api/groups/"


# Create your tests here.
class GroupTestCase(TestCase):
    """Test cases for the group endpoints."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.pre_save.disconnect(
            sender=DiscordRole,
            dispatch_uid="resolve_existing_discord_role_from_server",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )

        self.client = Client()
        super().setUp()

    def test_get_groups_success(self):
        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_groups_success_multiple_groups(self):
        group = Group.objects.create(name="Test Group")
        group = Group.objects.create(name="Test Group Hidden")
        self.user.groups.add(group)

        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": group.id,
                    "name": group.name,
                    "description": None,
                    "image_url": None,
                }
            ],
        )

    def test_get_groups_available_success(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)

        response = self.client.get(
            f"{BASE_URL}available", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": group.id,
                    "name": group.name,
                    "description": None,
                    "image_url": None,
                }
            ],
        )

    def test_get_groups_available_success_hide_unauthorized_group(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        hidden_group = Group.objects.create(name="Test Group Hidden")
        hidden_group_requestable_group = RequestableGroup.objects.create(
            group=hidden_group,
        )
        hidden_group_requestable_group.required_groups.add(group)

        response = self.client.get(
            f"{BASE_URL}available", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": group.id,
                    "name": group.name,
                    "description": None,
                    "image_url": None,
                }
            ],
        )

    def test_get_groups_avialable_success_show_authorized_group(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        self.user.groups.add(group)
        hidden_group = Group.objects.create(name="Test Group Hidden")
        hidden_group_requestable_group = RequestableGroup.objects.create(
            group=hidden_group,
        )
        hidden_group_requestable_group.required_groups.add(group)
        response = self.client.get(
            f"{BASE_URL}available", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        # assert that first group is in response
        self.assertTrue(
            {
                "id": group.id,
                "name": group.name,
                "description": None,
                "image_url": None,
            }
            in response.json()
        )
        # assert that second group is in response
        self.assertTrue(
            {
                "id": hidden_group.id,
                "name": hidden_group.name,
                "description": hidden_group_requestable_group.description,
                "image_url": hidden_group_requestable_group.image_url,
            }
            in response.json()
        )

    def test_get_group_users_success(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        requestable_group.group_managers.add(self.user)
        self.user.groups.add(group)

        response = self.client.get(
            f"{BASE_URL}{group.id}/users",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [self.user.id],
        )

    def test_get_group_users_failure_not_permitted(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        self.user.groups.add(group)

        response = self.client.get(
            f"{BASE_URL}{group.id}/users",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_get_group_users_failure_group_does_not_exist(self):
        response = self.client.get(
            f"{BASE_URL}999/users",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_group_user_success(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        requestable_group.group_managers.add(self.user)
        self.user.groups.add(group)
        user = User.objects.create(username="testuser")
        group.user_set.add(user)
        response = self.client.delete(
            f"{BASE_URL}{group.id}/users/{user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 204)


class GroupRequestTestCase(TestCase):
    """Test cases for the group request endpoints."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.pre_save.disconnect(
            sender=DiscordRole,
            dispatch_uid="resolve_existing_discord_role_from_server",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )

        self.client = Client()
        super().setUp()

    def test_get_group_requests_success(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        permission = Permission.objects.get(codename="view_grouprequest")
        self.user.user_permissions.add(permission)

        response = self.client.get(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        print(response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": request.id,
                    "user": self.user.id,
                    "group": group.id,
                    "approved": None,
                    "approved_by": None,
                    "approved_at": None,
                }
            ],
        )

    def test_get_group_requests_success_group_manager(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.get(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": request.id,
                    "user": self.user.id,
                    "group": group.id,
                    "approved": None,
                    "approved_by": None,
                    "approved_at": None,
                }
            ],
        )

    def test_get_group_requests_failure_unauthorized(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        GroupRequest.objects.create(
            user=self.user,
            group=group,
        )

        response = self.client.get(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_get_group_requests_failure_not_requestable(self):
        group = Group.objects.create(name="Test Group")
        response = self.client.get(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_group_request_success(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "id": 1,
                "user": self.user.id,
                "group": group.id,
                "approved": None,
                "approved_by": None,
                "approved_at": None,
            },
        )

    def test_create_group_request_failure_already_requested(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        GroupRequest.objects.create(
            user=self.user,
            group=group,
        )

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_group_request_failure_not_requestable(self):
        group = Group.objects.create(name="Test Group")

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_group_request_failure_not_permitted(self):
        group = Group.objects.create(name="Unpermitted Test Group")
        required_group = Group.objects.create(name="Test Group Required")
        r = RequestableGroup.objects.create(group=group)
        r.required_groups.add(required_group)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_group_request_success(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": request.id,
                "user": self.user.id,
                "group": group.id,
                "approved": True,
                "approved_by": self.user.id,
                "approved_at": request.approved_at,
            },
        )

    def test_approve_group_request_failure_already_approved(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
            approved=True,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_group_request_failure_not_permitted(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_approve_group_request_failure_group_does_not_exist(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}999/requests/{request.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_group_request_failure_request_does_not_exist(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/999/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_group_request_failure_group_not_requestable(self):
        group = Group.objects.create(name="Test Group")
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_deny_group_request_success(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": request.id,
                "user": self.user.id,
                "group": group.id,
                "approved": False,
                "approved_by": self.user.id,
                "approved_at": request.approved_at,
            },
        )

    def test_deny_group_request_failure_already_approved(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
            approved=True,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_deny_group_request_failure_not_permitted(self):
        group = Group.objects.create(name="Test Group")
        RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_deny_group_request_failure_group_does_not_exist(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}999/requests/{request.id}/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_deny_group_request_failure_request_does_not_exist(self):
        group = Group.objects.create(name="Test Group")
        requestable_group = RequestableGroup.objects.create(group=group)
        GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        requestable_group.group_managers.add(self.user)

        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/999/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_deny_group_request_failure_group_not_requestable(self):
        group = Group.objects.create(name="Test Group")
        request = GroupRequest.objects.create(
            user=self.user,
            group=group,
        )
        response = self.client.post(
            f"{BASE_URL}{group.id}/requests/{request.id}/deny",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
