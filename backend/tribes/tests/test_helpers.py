"""Tests for tribes helpers."""

from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterSkill
from eveuniverse.models import EveCategory, EveGroup, EveType

from tribes.helpers import (
    check_character_meets_requirements,
    user_can_manage_group,
    user_in_tribe_group,
    user_is_tribe_chief,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupRequirement,
    TribeGroupRequirementSkill,
)


def setUpModule():
    """Disconnect the Discord group-change signal that requires a linked DiscordUser."""
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


def make_eve_type(type_id: int, name: str) -> EveType:
    """Create a minimal EveType for testing."""
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=99001,
        defaults={
            "name": "Test Category",
            "last_updated": now,
            "published": True,
        },
    )
    group, _ = EveGroup.objects.get_or_create(
        id=99001,
        defaults={
            "name": "Test Group",
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    eve_type, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "last_updated": now,
            "published": True,
            "eve_group": group,
        },
    )
    return eve_type


class CheckRequirementsTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads"
        )
        self.user = User.objects.create_user(username="pilot")
        self.character = EveCharacter.objects.create(
            character_id=99001, character_name="Test Pilot", user=self.user
        )

    def test_skill_requirement_met(self):
        skill_eve_type = make_eve_type(23950, "Capital Ships")
        EveCharacterSkill.objects.create(
            character=self.character,
            skill_id=23950,
            skill_name="Capital Ships",
            skill_level=5,
            skill_points=24000000,
        )
        req = TribeGroupRequirement.objects.create(
            tribe_group=self.tribe_group,
            requirement_type=TribeGroupRequirement.REQUIREMENT_TYPE_SKILL,
        )
        TribeGroupRequirementSkill.objects.create(
            requirement=req,
            eve_type=skill_eve_type,
            minimum_level=5,
        )
        snapshot = check_character_meets_requirements(
            self.character, self.tribe_group
        )
        self.assertTrue(snapshot[str(req.pk)]["met"])
        self.assertIn("All skills met", snapshot[str(req.pk)]["detail"])

    def test_skill_requirement_not_met(self):
        skill_eve_type = make_eve_type(23950, "Capital Ships")
        EveCharacterSkill.objects.create(
            character=self.character,
            skill_id=23950,
            skill_name="Capital Ships",
            skill_level=3,
            skill_points=500000,
        )
        req = TribeGroupRequirement.objects.create(
            tribe_group=self.tribe_group,
            requirement_type=TribeGroupRequirement.REQUIREMENT_TYPE_SKILL,
        )
        TribeGroupRequirementSkill.objects.create(
            requirement=req,
            eve_type=skill_eve_type,
            minimum_level=5,
        )
        snapshot = check_character_meets_requirements(
            self.character, self.tribe_group
        )
        self.assertFalse(snapshot[str(req.pk)]["met"])
        self.assertIn("Missing", snapshot[str(req.pk)]["detail"])

    def test_no_requirements_returns_empty_snapshot(self):
        snapshot = check_character_meets_requirements(
            self.character, self.tribe_group
        )
        self.assertEqual(snapshot, {})


class UserPermissionHelpersTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads"
        )
        self.chief = User.objects.create_user(username="tribe_chief")
        self.group_chief = User.objects.create_user(username="group_chief")
        self.elder = User.objects.create_user(username="elder")
        self.regular = User.objects.create_user(username="regular")

        self.tribe.chief = self.chief
        self.tribe.save()
        self.tribe_group.chief = self.group_chief
        self.tribe_group.save()
        self.tribe_group.elders.add(self.elder)

    def test_tribe_chief_can_manage_group(self):
        self.assertTrue(user_can_manage_group(self.chief, self.tribe_group))

    def test_group_chief_can_manage_group(self):
        self.assertTrue(
            user_can_manage_group(self.group_chief, self.tribe_group)
        )

    def test_elder_can_manage_group(self):
        self.assertTrue(user_can_manage_group(self.elder, self.tribe_group))

    def test_regular_cannot_manage_group(self):
        self.assertFalse(user_can_manage_group(self.regular, self.tribe_group))

    def test_superuser_can_manage_group(self):
        self.regular.is_superuser = True
        self.regular.save()
        self.assertTrue(user_can_manage_group(self.regular, self.tribe_group))

    def test_user_is_tribe_chief(self):
        self.assertTrue(user_is_tribe_chief(self.chief, self.tribe))
        self.assertFalse(user_is_tribe_chief(self.regular, self.tribe))

    def test_user_in_tribe_group(self):
        TribeGroupMembership.objects.create(
            user=self.regular,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_APPROVED,
        )
        self.assertTrue(user_in_tribe_group(self.regular, self.tribe_group))
        self.assertFalse(user_in_tribe_group(self.chief, self.tribe_group))

    def test_user_in_tribe_group_pending_not_counted(self):
        TribeGroupMembership.objects.create(
            user=self.regular,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_PENDING,
        )
        self.assertFalse(user_in_tribe_group(self.regular, self.tribe_group))
