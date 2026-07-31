from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.models import EveCharacter, EveCharacterIndustryJob
from industry.helpers.notifications import (
    match_industry_job_to_assignment,
    new_order_audience,
    users_active_in_tribe_groups,
    users_participated_in_orders_since,
)
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from notifications.models import NotificationTopicSubscription
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


def _make_type(type_id: int, name: str) -> EveType:
    cat, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=25,
        defaults={
            "name": "Frigate",
            "published": True,
            "eve_category": cat,
        },
    )
    eve_type, created = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "published": True,
            "eve_group": group,
        },
    )
    if not created and (
        not eve_type.published or eve_type.eve_group_id is None
    ):
        eve_type.published = True
        eve_type.eve_group = group
        eve_type.save(update_fields=["published", "eve_group"])
    return eve_type


class AudienceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user("owner", password="x")
        self.assignee = User.objects.create_user("assignee", password="x")
        self.subscriber = User.objects.create_user("sub", password="x")
        self.owner_char = EveCharacter.objects.create(
            character_id=910101,
            character_name="Owner Char",
            user=self.owner,
        )
        self.assignee_char = EveCharacter.objects.create(
            character_id=910102,
            character_name="Assignee Char",
            user=self.assignee,
        )
        self.eve_type = _make_type(587, "Rifter")
        self.order = IndustryOrder.objects.create(
            needed_by=timezone.now().date() + timedelta(days=7),
            character=self.owner_char,
            public_short_code="ZZZ",
        )
        item = IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.eve_type, quantity=10
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item, character=self.assignee_char, quantity=5
        )
        NotificationTopicSubscription.objects.create(
            user=self.subscriber, notification_type="industry.order.created"
        )

    def test_participants_include_owner_and_assignee(self):
        users = users_participated_in_orders_since(
            timezone.now() - timedelta(days=30)
        )
        self.assertIn(self.owner.id, users)
        self.assertIn(self.assignee.id, users)

    def test_new_order_audience_unions_topic_subscribers(self):
        audience = new_order_audience(
            self.order, exclude_user_id=self.owner.id
        )
        self.assertNotIn(self.owner.id, audience)
        self.assertIn(self.assignee.id, audience)
        self.assertIn(self.subscriber.id, audience)

    def test_new_order_audience_includes_active_tribe_group_members(self):
        member = User.objects.create_user("tribemember", password="x")
        outsider = User.objects.create_user("outsider", password="x")
        tribe = Tribe.objects.create(name="Supply", slug="supply-notif")
        group = TribeGroup.objects.create(
            tribe=tribe, name="Manufacturing", code="supply.mfg.notif"
        )
        TribeGroupMembership.objects.create(
            user=member,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembership.objects.create(
            user=outsider,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_PENDING,
        )
        self.order.tribe_groups.add(group)

        self.assertEqual(users_active_in_tribe_groups([group.pk]), {member.id})
        audience = new_order_audience(
            self.order, exclude_user_id=self.owner.id
        )
        self.assertIn(member.id, audience)
        self.assertNotIn(outsider.id, audience)


class JobMatchTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("builder", password="x")
        self.char = EveCharacter.objects.create(
            character_id=910201,
            character_name="Builder",
            user=self.user,
        )
        self.product = _make_type(587, "Rifter")
        self.order = IndustryOrder.objects.create(
            needed_by=timezone.now().date() + timedelta(days=7),
            character=self.char,
            public_short_code="JOB",
        )
        self.item = IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.product, quantity=1
        )
        self.assignment = IndustryOrderItemAssignment.objects.create(
            order_item=self.item, character=self.char, quantity=1
        )

    @patch(
        "industry.helpers.notifications.blueprint_activity_pairs_for_product_type",
        return_value={(999, 1)},
    )
    def test_match_when_blueprint_produces_line(self, mock_pairs):
        del mock_pairs
        now = timezone.now()
        job = EveCharacterIndustryJob.objects.create(
            job_id=555001,
            character=self.char,
            activity_id=1,
            blueprint_id=1,
            blueprint_type_id=999,
            blueprint_location_id=1,
            facility_id=1,
            location_id=1,
            output_location_id=1,
            status="active",
            installer_id=self.char.character_id,
            start_date=now,
            end_date=now + timedelta(hours=2),
            duration=7200,
            runs=1,
        )
        matched = match_industry_job_to_assignment(job)
        self.assertEqual(matched.pk, self.assignment.pk)

    @patch(
        "industry.helpers.notifications.blueprint_activity_pairs_for_product_type",
        return_value={(999, 1)},
    )
    def test_no_match_wrong_blueprint(self, mock_pairs):
        del mock_pairs
        now = timezone.now()
        job = EveCharacterIndustryJob.objects.create(
            job_id=555002,
            character=self.char,
            activity_id=1,
            blueprint_id=1,
            blueprint_type_id=111,
            blueprint_location_id=1,
            facility_id=1,
            location_id=1,
            output_location_id=1,
            status="active",
            installer_id=self.char.character_id,
            start_date=now,
            end_date=now + timedelta(hours=2),
            duration=7200,
            runs=1,
        )
        self.assertIsNone(match_industry_job_to_assignment(job))

    @patch(
        "industry.helpers.notifications.blueprint_activity_pairs_for_product_type",
        return_value={(999, 1)},
    )
    def test_no_match_completed_job(self, mock_pairs):
        del mock_pairs
        now = timezone.now()
        job = EveCharacterIndustryJob.objects.create(
            job_id=555004,
            character=self.char,
            activity_id=1,
            blueprint_id=1,
            blueprint_type_id=999,
            blueprint_location_id=1,
            facility_id=1,
            location_id=1,
            output_location_id=1,
            status="delivered",
            installer_id=self.char.character_id,
            start_date=now - timedelta(hours=3),
            end_date=now - timedelta(hours=1),
            completed_date=now - timedelta(hours=1),
            duration=7200,
            runs=1,
        )
        self.assertIsNone(match_industry_job_to_assignment(job))

    @patch(
        "industry.helpers.notifications.blueprint_activity_pairs_for_product_type",
        return_value={(999, 1)},
    )
    def test_match_prefers_job_character_over_older_alt_claim(
        self, mock_pairs
    ):
        del mock_pairs
        alt = EveCharacter.objects.create(
            character_id=910202,
            character_name="Builder Alt",
            user=self.user,
        )
        older_order = IndustryOrder.objects.create(
            needed_by=timezone.now().date() + timedelta(days=7),
            character=self.char,
            public_short_code="OLD",
        )
        older_item = IndustryOrderItem.objects.create(
            order=older_order, eve_type=self.product, quantity=1
        )
        # Older claim on alt (lower pk) vs newer claim on job character.
        IndustryOrderItemAssignment.objects.create(
            order_item=older_item, character=alt, quantity=1
        )
        now = timezone.now()
        job = EveCharacterIndustryJob.objects.create(
            job_id=555003,
            character=self.char,
            activity_id=1,
            blueprint_id=1,
            blueprint_type_id=999,
            blueprint_location_id=1,
            facility_id=1,
            location_id=1,
            output_location_id=1,
            status="active",
            installer_id=self.char.character_id,
            start_date=now,
            end_date=now + timedelta(hours=2),
            duration=7200,
            runs=1,
        )
        matched = match_industry_job_to_assignment(job)
        self.assertEqual(matched.pk, self.assignment.pk)
        self.assertEqual(matched.character_id, self.char.pk)
