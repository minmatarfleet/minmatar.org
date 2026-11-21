from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.models import EveLocation
from groups.helpers.feature_access import clear_feature_cache

URL = "/api/structures/locations/stagings"


def make_location(location_id, name, short_name, **flags):
    flags.setdefault("audience", EveLocation.AUDIENCE_PUBLIC)
    return EveLocation.objects.create(
        location_id=location_id,
        location_name=name,
        solar_system_id=30000000 + location_id,
        solar_system_name=f"System {short_name}",
        short_name=short_name,
        **flags,
    )


class StagingsEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        self.home = make_location(
            1, "Home Station - Example", "Home", staging_active=True
        )

    def test_no_deployment_lists_only_home(self):
        body = self.client.get(URL).json()
        self.assertEqual(body["home"]["short_name"], "Home")
        self.assertEqual(body["deployments"], [])

    def test_lists_deployments_but_not_other_locations(self):
        make_location(2, "Forward Station", "Forward", deployment_active=True)
        make_location(3, "Elsewhere Station", "Elsewhere")
        body = self.client.get(URL).json()
        self.assertEqual(
            [row["short_name"] for row in body["deployments"]], ["Forward"]
        )
        self.assertEqual(
            body["deployments"][0]["solar_system_name"], "System Forward"
        )

    def test_no_staging_gives_null_home(self):
        self.home.delete()
        cache.clear()
        self.assertIsNone(self.client.get(URL).json()["home"])

    def test_alliance_only_deployment_hidden_from_signed_out(self):
        make_location(
            2,
            "Forward Station",
            "Forward",
            deployment_active=True,
            audience=EveLocation.AUDIENCE_ALLIANCE,
        )
        self.home.audience = EveLocation.AUDIENCE_PUBLIC
        self.home.save()
        cache.clear()
        anonymous = self.client.get(URL).json()
        self.assertEqual(anonymous["deployments"], [])
        self.assertEqual(anonymous["home"]["short_name"], "Home")

        self.user.user_permissions.add(
            Permission.objects.get(
                codename="view_evestructure",
                content_type__app_label="structures",
            )
        )
        clear_feature_cache()
        member = self.client.get(
            URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        ).json()
        self.assertEqual(len(member["deployments"]), 1)
