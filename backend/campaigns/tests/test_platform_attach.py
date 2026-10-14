"""Optional campaign FK on industry orders and blog posts."""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.utils import timezone

from app.test import TestCase
from campaigns.models import CampaignKind, CampaignStatus
from campaigns.tests.helpers import make_campaign
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType
from industry.models import IndustryOrder
from posts.models import EvePost


class CampaignPlatformAttachTests(TestCase):
    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.campaign = make_campaign(
            slug="cva-pressure",
            short_code="CVA",
            name="CVA Pressure",
            kind=CampaignKind.STRATEGIC,
            status=CampaignStatus.ACTIVE,
        )
        self.completed = make_campaign(
            slug="done-push",
            short_code="DON",
            name="Done Push",
            status=CampaignStatus.COMPLETED,
            start_at=timezone.now() - timedelta(days=40),
            end_at=timezone.now() - timedelta(days=10),
        )
        self.character = EveCharacter.objects.create(
            character_id=991001,
            character_name="Order Tester",
            user=self.user,
        )
        set_primary_character(self.user, self.character)
        category, _ = EveCategory.objects.get_or_create(
            id=91, defaults={"name": "Attach Cat", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=91,
            defaults={
                "name": "Attach Group",
                "published": True,
                "eve_category": category,
            },
        )
        self.eve_type = EveType.objects.create(
            id=991201,
            name="Typhoon",
            published=True,
            eve_group=group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999101,
            location_name="Attach Station",
            solar_system_id=300001,
            solar_system_name="Jita",
            short_name="ATT",
            staging_active=True,
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evepost")
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="change_evepost")
        )

    def test_create_post_with_campaign(self):
        response = self.client.post(
            "/api/blog/posts",
            {
                "title": "CVA propaganda",
                "state": "draft",
                "seo_description": "For the push",
                "content": "Bash the Fortizar",
                "tag_ids": [],
                "campaign_id": self.campaign.id,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["campaign_id"], self.campaign.id)
        self.assertEqual(body["campaign_slug"], "cva-pressure")
        post = EvePost.objects.get(pk=body["post_id"])
        self.assertEqual(post.campaign_id, self.campaign.id)

    def test_filter_posts_by_campaign(self):
        matched = EvePost.objects.create(
            title="Matched",
            state="published",
            seo_description="m",
            slug="matched",
            content="body",
            user=self.user,
            campaign=self.campaign,
        )
        EvePost.objects.create(
            title="Other",
            state="published",
            seo_description="o",
            slug="other",
            content="body",
            user=self.user,
        )
        response = self.client.get(
            "/api/blog/posts",
            {"campaign_id": self.campaign.id, "status": "published"},
        )
        self.assertEqual(response.status_code, 200)
        posts = response.json()
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["post_id"], matched.id)

    def test_patch_post_clears_campaign(self):
        post = EvePost.objects.create(
            title="Clear me",
            state="draft",
            seo_description="c",
            slug="clear-me",
            content="body",
            user=self.user,
            campaign=self.campaign,
        )
        response = self.client.patch(
            f"/api/blog/posts/{post.id}",
            data=json.dumps({"campaign_id": None}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        post.refresh_from_db()
        self.assertIsNone(post.campaign_id)

    def test_create_order_with_campaign(self):
        needed = (timezone.now() + timedelta(days=14)).date().isoformat()
        response = self.client.post(
            "/api/industry/orders",
            data=json.dumps(
                {
                    "needed_by": needed,
                    "character_id": self.character.character_id,
                    "location_id": self.location.location_id,
                    "contract_to": self.character.character_name,
                    "campaign_id": self.campaign.id,
                    "items": [
                        {"eve_type_id": self.eve_type.id, "quantity": 2}
                    ],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        order = IndustryOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.campaign_id, self.campaign.id)

        detail = self.client.get(f"/api/industry/orders/{order.pk}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["campaign_slug"], "cva-pressure")

    def test_patch_order_campaign_rejects_completed(self):
        needed = (timezone.now() + timedelta(days=14)).date()
        order = IndustryOrder.objects.create(
            needed_by=needed,
            character=self.character,
            location=self.location,
            contract_to=self.character.character_name,
            public_short_code="ZZZ",
        )
        response = self.client.patch(
            f"/api/industry/orders/{order.pk}",
            data=json.dumps({"campaign_id": self.completed.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertIsNone(order.campaign_id)
