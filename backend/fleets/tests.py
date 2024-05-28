from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCorporation

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
