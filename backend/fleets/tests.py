from datetime import datetime

from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCorporation
from fleets.models import EveFleet, EveFleetNotificationChannel
from structures.models import EveStructure

BASE_URL = "/api/fleets"


class FleetRouterTestCase(TestCase):
    """Test cases for the fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )

        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )

        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )

        super().setUp()

    def test_get_fleet_types_success(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )
        response = self.client.get(
            f"{BASE_URL}/types", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), ["stratop", "non_strategic", "casual", "training"]
        )

    def test_get_fleet_locations_success(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )
        corporation = EveCorporation.objects.create(
            id=98741376,
            corporation_id=98741376,
        )
        EveStructure.objects.create(
            id=1,
            system_id=30000142,
            system_name="Jita",
            type_id=35832,
            type_name="Astrahus",
            name="Test Structure",
            is_valid_staging=True,
            reinforce_hour=13,
            corporation=corporation,
        )
        EveStructure.objects.create(
            id=2,
            system_id=30000142,
            system_name="Jita",
            type_id=35832,
            type_name="Astrahus",
            name="Test Structure 2",
            is_valid_staging=False,
            reinforce_hour=13,
            corporation=corporation,
        )
        response = self.client.get(
            f"{BASE_URL}/locations", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Test Structure"])

    def test_get_fleets_success(self):
        fleet = EveFleet.objects.create(
            description="Test Fleet",
            type="stratop",
            start_time="2021-01-01T00:00:00Z",
            created_by=self.user,
        )
        response = self.client.get(
            f"{BASE_URL}?upcoming=False",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [fleet.id])

    def test_create_fleet_success(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )
        # set up audience
        group = Group.objects.create(name="Pingable Group")
        EveFleetNotificationChannel.objects.create(
            group=group,
            discord_channel_name="pingable",
            discord_channel_id=123456789,
        )
        payload = {
            "type": "stratop",
            "description": "Test Fleet",
            "start_time": datetime.now().isoformat() + "Z",
            "location": "Test Structure",
            "audience_id": group.id,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["type"], "stratop")
        self.assertEqual(response.json()["description"], "Test Fleet")
        self.assertEqual(response.json()["location"], "Test Structure")
        fleets = EveFleet.objects.all()
        self.assertEqual(len(fleets), 1)

    def test_get_fleet_success(self):
        fleet = EveFleet.objects.create(
            description="Test Fleet",
            type="stratop",
            start_time="2021-01-01T00:00:00Z",
            created_by=self.user,
        )
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": fleet.id,
                "type": "stratop",
                "description": "Test Fleet",
                "start_time": "2021-01-01T00:00:00Z",
                "fleet_commander": self.user.id,
                "doctrine_id": None,
                "location": "",
            },
        )

    def test_get_fleet_success_member_of_group(self):
        group = Group.objects.create(name="Test Group")
        self.user.groups.add(group)
        start_time = (
            datetime.now().replace(second=0, microsecond=0).isoformat() + "Z"
        )
        fleet = EveFleet.objects.create(
            description="Test Fleet",
            type="stratop",
            start_time=start_time,
            created_by=User.objects.create_user(username="hausdfhiusaihu"),
            audience=group,
        )
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": fleet.id,
                "type": "stratop",
                "description": "Test Fleet",
                "start_time": start_time,
                "fleet_commander": fleet.created_by.id,
                "doctrine_id": None,
                "location": "",
            },
        )

    def test_get_fleet_sucess_permission_override(self):
        fleet = EveFleet.objects.create(
            description="Test Fleet",
            type="stratop",
            start_time="2021-01-01T00:00:00Z",
            created_by=User.objects.create_user(username="bbadsfasdf"),
        )
        permission = Permission.objects.get(codename="view_evefleet")
        self.user.user_permissions.add(permission)
        self.user.save()
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": fleet.id,
                "type": "stratop",
                "description": "Test Fleet",
                "start_time": "2021-01-01T00:00:00Z",
                "fleet_commander": fleet.created_by.id,
                "doctrine_id": None,
                "location": "",
            },
        )

    def test_get_fleet_failure_unauthorized(self):
        fleet = EveFleet.objects.create(
            description="Test Fleet",
            type="stratop",
            start_time="2021-01-01T00:00:00Z",
            created_by=User.objects.create_user(username="abbgsdfgsdf"),
        )
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 403)
