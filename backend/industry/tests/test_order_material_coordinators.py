"""Tests for mineral / PI order coordinators and fixed catalog options."""

import json
from datetime import timedelta

from django.utils import timezone
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from eveuniverse.models import EveCategory, EveGroup, EveType
from unittest.mock import patch

from app.test import TestCase as AppTestCase
from industry.helpers.order_coordinator_materials import (
    BASIC_MINERAL_TYPE_IDS,
    NAVY_HULL_PI_TYPE_IDS,
    order_mineral_and_pi_options,
    validate_mineral_coordinator_eve_type_ids,
    validate_pi_coordinator_eve_type_ids,
)
from industry.models import (
    IndustryOrderItem,
    IndustryOrderMineralCoordinator,
    IndustryOrderPiCoordinator,
)
from industry.test_utils import create_industry_order


class MineralPiCoordinatorApiTestCase(AppTestCase):
    """POST/PATCH/DELETE mineral and PI coordinators; fixed option catalogs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eve_category, _ = EveCategory.objects.get_or_create(
            id=1, defaults={"name": "Test Category", "published": True}
        )
        cls.eve_group, _ = EveGroup.objects.get_or_create(
            id=1,
            defaults={
                "name": "Test Group",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )

    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.get_or_create(
            character_id=912001,
            defaults={"character_name": "Mineral Coord", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.ship = EveType.objects.create(
            id=912101,
            name="Coord Hull",
            published=True,
            eve_group=self.eve_group,
        )
        self.trit, _ = EveType.objects.get_or_create(
            id=34,
            defaults={
                "name": "Tritanium",
                "published": True,
                "eve_group": self.eve_group,
            },
        )
        self.pye, _ = EveType.objects.get_or_create(
            id=35,
            defaults={
                "name": "Pyerite",
                "published": True,
                "eve_group": self.eve_group,
            },
        )
        self.hydro, _ = EveType.objects.get_or_create(
            id=16633,
            defaults={
                "name": "Hydrocarbons",
                "published": True,
                "eve_group": self.eve_group,
            },
        )
        self.coolant, _ = EveType.objects.get_or_create(
            id=9832,
            defaults={
                "name": "Coolant",
                "published": True,
                "eve_group": self.eve_group,
            },
        )
        self.order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.ship, quantity=5
        )

    def test_validate_mineral_rejects_non_mineral(self):
        err = validate_mineral_coordinator_eve_type_ids(
            self.order, [self.hydro.id]
        )
        self.assertIsNotNone(err)
        self.assertIn(str(self.hydro.id), err)

    def test_validate_pi_rejects_mineral(self):
        err = validate_pi_coordinator_eve_type_ids(self.order, [self.trit.id])
        self.assertIsNotNone(err)
        self.assertIn(str(self.trit.id), err)

    def test_fixed_catalog_options(self):
        minerals, pi = order_mineral_and_pi_options()
        self.assertEqual(
            {t.id for t in minerals},
            set(BASIC_MINERAL_TYPE_IDS) & {self.trit.id, self.pye.id},
        )
        self.assertEqual(
            {t.id for t in pi},
            set(NAVY_HULL_PI_TYPE_IDS) & {self.hydro.id, self.coolant.id},
        )

    def test_post_mineral_coordinator(self):
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/mineral-coordinators",
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.trit.id, self.pye.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["character_id"], self.character.character_id)
        self.assertEqual(len(data["eve_types"]), 2)
        self.assertEqual(
            IndustryOrderMineralCoordinator.objects.filter(
                order=self.order
            ).count(),
            1,
        )

    def test_post_mineral_upserts(self):
        url = f"/api/industry/orders/{self.order.pk}/mineral-coordinators"
        self.client.post(
            url,
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.trit.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.pye.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["eve_types"]), 1)
        self.assertEqual(
            response.json()["eve_types"][0]["eve_type_id"], self.pye.id
        )
        self.assertEqual(
            IndustryOrderMineralCoordinator.objects.filter(
                order=self.order
            ).count(),
            1,
        )

    def test_post_mineral_rejects_pi_type(self):
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/mineral-coordinators",
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.hydro.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_pi_coordinator(self):
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/pi-coordinators",
            data=json.dumps(
                {
                    "character_id": self.character.character_id,
                    "eve_type_ids": [self.hydro.id, self.coolant.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(len(data["eve_types"]), 2)
        self.assertEqual(
            IndustryOrderPiCoordinator.objects.filter(
                order=self.order
            ).count(),
            1,
        )

    def test_post_pi_rejects_foreign_character(self):
        other_user = self.user.__class__.objects.create(username="pi_foreign")
        foreign = EveCharacter.objects.create(
            character_id=912003,
            character_name="Foreign PI",
            user=other_user,
        )
        response = self.client.post(
            f"/api/industry/orders/{self.order.pk}/pi-coordinators",
            data=json.dumps(
                {
                    "character_id": foreign.character_id,
                    "eve_type_ids": [self.hydro.id],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_patch_and_delete_mineral(self):
        coordinator = IndustryOrderMineralCoordinator.objects.create(
            order=self.order, character=self.character
        )
        coordinator.eve_types.set([self.trit])

        patch_response = self.client.patch(
            f"/api/industry/orders/{self.order.pk}/mineral-coordinators/"
            f"{coordinator.pk}",
            data=json.dumps({"eve_type_ids": [self.pye.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(
            patch_response.status_code, 200, patch_response.content
        )
        self.assertEqual(
            patch_response.json()["eve_types"][0]["eve_type_id"], self.pye.id
        )

        delete = self.client.delete(
            f"/api/industry/orders/{self.order.pk}/mineral-coordinators/"
            f"{coordinator.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            IndustryOrderMineralCoordinator.objects.filter(
                pk=coordinator.pk
            ).exists()
        )

    def test_patch_and_delete_pi(self):
        coordinator = IndustryOrderPiCoordinator.objects.create(
            order=self.order, character=self.character
        )
        coordinator.eve_types.set([self.hydro])

        patch_response = self.client.patch(
            f"/api/industry/orders/{self.order.pk}/pi-coordinators/"
            f"{coordinator.pk}",
            data=json.dumps({"eve_type_ids": [self.coolant.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(
            patch_response.status_code, 200, patch_response.content
        )
        self.assertEqual(
            patch_response.json()["eve_types"][0]["eve_type_id"],
            self.coolant.id,
        )

        delete = self.client.delete(
            f"/api/industry/orders/{self.order.pk}/pi-coordinators/"
            f"{coordinator.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            IndustryOrderPiCoordinator.objects.filter(
                pk=coordinator.pk
            ).exists()
        )

    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_order_detail_includes_mineral_pi_coordinators(self, mock_sync):
        mineral = IndustryOrderMineralCoordinator.objects.create(
            order=self.order, character=self.character
        )
        mineral.eve_types.set([self.trit])
        pi = IndustryOrderPiCoordinator.objects.create(
            order=self.order, character=self.character
        )
        pi.eve_types.set([self.hydro])

        response = self.client.get(f"/api/industry/orders/{self.order.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["mineral_coordinators"]), 1)
        self.assertEqual(len(data["pi_coordinators"]), 1)
        # Options are lazy via material-options, not on the hot get_order path.
        self.assertEqual(data["mineral_options"], [])
        self.assertEqual(data["pi_options"], [])

    def test_material_options_endpoint(self):
        response = self.client.get(
            f"/api/industry/orders/{self.order.pk}/material-options"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        mineral_ids = {o["eve_type_id"] for o in data["mineral_options"]}
        pi_ids = {o["eve_type_id"] for o in data["pi_options"]}
        self.assertIn(self.trit.id, mineral_ids)
        self.assertIn(self.pye.id, mineral_ids)
        self.assertIn(self.hydro.id, pi_ids)
        self.assertIn(self.coolant.id, pi_ids)
        self.assertNotIn(self.hydro.id, mineral_ids)
        self.assertNotIn(self.trit.id, pi_ids)
