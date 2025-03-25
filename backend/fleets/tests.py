import datetime

from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client
from esi.models import Token

from app.test import TestCase
from eveonline.models import EveCorporation, EveCharacter, EvePrimaryCharacter
from fleets.models import EveFleet

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

        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )

        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )

        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        super().setUp()

    def test_fleet_commander(self):
        fc_user = User.objects.first()
        token = Token.objects.create(
            user=fc_user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Mr FC",
            token=token,
        )
        EvePrimaryCharacter.objects.create(
            character=char,
        )
        fleet = EveFleet.objects.create(
            description="Test fleet 1",
            start_time=datetime.datetime.now(),
            created_by=fc_user,
        )
        self.assertEqual("Mr FC", fleet.fleet_commander.character_name)
