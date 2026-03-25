import factory

from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client
from esi.models import Token

from app.test import TestCase
from tech.testdata import minmil_faction
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
)
from eveonline.helpers.characters import set_primary_character
from discord.models import DiscordUser
from groups.models import (
    AffiliationType,
    UserAffiliation,
    EveCorporationGroup,
)
from groups.helpers import (
    TRIBE_CHIEF_GROUP_NAME,
    sync_tribe_chief_group_membership,
)
from groups.tasks import (
    update_affiliations,
    sync_eve_corporation_groups,
)
from tribes.models import Tribe, TribeGroup


class UserAffiliationTestCase(TestCase):
    """
    E2E tests for the UserAffiliation setting of auto groups
    """

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        signals.post_save.disconnect(
            sender=EveAlliance,
            dispatch_uid="eve_alliance_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def test_set_user_affiliation_success(self):
        # set up data
        user = User.objects.create(
            username="test_set_user_affiliation_success"
        )
        group = Group.objects.create(name="test_set_user_affiliation_success")
        corporation = EveCorporation.objects.create(corporation_id=98726134)
        alliance = EveAlliance.objects.create(alliance_id=99011978)
        faction = minmil_faction()
        character = EveCharacter.objects.create(character_id=123)
        token = Token.objects.create(
            character_id=123,
            user=user,
        )
        character.token = token
        character.save()
        set_primary_character(user, character)
        affiliation_type = AffiliationType.objects.create(
            name="Example",
            description="Example",
            image_url="https://example.com/image.png",
            group=group,
            priority=1,
        )
        affiliation_type.corporations.add(corporation)
        affiliation_type.alliances.add(alliance)
        affiliation_type.factions.add(faction)

        # create affiliations
        update_affiliations()
        user_affiliation = UserAffiliation.objects.filter(user=user).first()
        assert user_affiliation is None

        # qualify by corporation
        character.corporation_id = corporation.corporation_id
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.corporation_id = None
        character.save()
        user_affiliation.delete()

        # qualify by alliance
        character.alliance_id = alliance.alliance_id
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.alliance_id = None
        character.save()
        user_affiliation.delete()

        # qualify by faction
        character.faction_id = faction.id
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.faction_id = None
        character.save()
        user_affiliation.delete()

        # remove if not qualified
        character.faction_id = faction.id
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.faction_id = None
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.filter(user=user).first()
        assert user_affiliation is None

    def test_set_user_affiliation_multiple_affiliations(self):
        # set up data
        user = User.objects.create(
            username="test_set_user_affiliation_multiple_affiliations"
        )
        group = Group.objects.create(
            name="test_set_user_affiliation_multiple_affiliations"
        )
        group_2 = Group.objects.create(
            name="test_set_user_affiliation_multiple_affiliations_2"
        )
        corporation = EveCorporation.objects.create(corporation_id=98726134)
        character = EveCharacter.objects.create(character_id=123)
        token = Token.objects.create(
            character_id=123,
            user=user,
        )
        character.token = token
        character.save()
        set_primary_character(user, character)
        affiliation_type = AffiliationType.objects.create(
            name="Example",
            description="Example",
            image_url="https://example.com/image.png",
            group=group,
            priority=1,
        )
        affiliation_type_2 = AffiliationType.objects.create(
            name="Example",
            description="Example",
            image_url="https://example.com/image.png",
            group=group_2,
            priority=5,
        )
        affiliation_type.corporations.add(corporation)
        affiliation_type_2.corporations.add(corporation)

        # qualify by corporation
        character.corporation_id = corporation.corporation_id
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type_2


class GroupTasksTestCase(TestCase):
    """Unit tests for Groups tasks"""

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_eve_corporation_groups(self):
        corp = EveCorporation.objects.create(
            corporation_id=100001,
            name="MegaCorp",
        )
        EveCorporationGroup.objects.create(
            corporation=corp,
            group=Group.objects.create(name=f"{corp.name} group"),
        )
        char = EveCharacter.objects.create(
            character_id=1001,
            character_name="Test Pilot",
            corporation_id=corp.corporation_id,
        )
        DiscordUser.objects.create(
            id=1000000001,
            user=self.user,
            discord_tag="testpilot",
        )
        set_primary_character(self.user, char)

        self.assertEqual(0, self.user.groups.count())

        sync_eve_corporation_groups()

        self.assertEqual(1, self.user.groups.count())
        self.assertEqual(f"{corp.name} group", self.user.groups.all()[0].name)


class SyncTribeChiefGroupTestCase(TestCase):
    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_adds_active_tribe_chief_and_creates_group(self):
        chief = User.objects.create_user(username="tribe_chief_sync")
        Tribe.objects.create(
            name="Mining",
            slug="mining",
            chief=chief,
        )
        self.assertFalse(
            Group.objects.filter(name=TRIBE_CHIEF_GROUP_NAME).exists()
        )
        self.assertEqual(0, chief.groups.count())

        sync_tribe_chief_group_membership()

        chief_group = Group.objects.get(name=TRIBE_CHIEF_GROUP_NAME)
        self.assertIn(chief_group, chief.groups.all())

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_removes_when_chief_cleared(self):
        chief = User.objects.create_user(username="former_chief")
        tribe = Tribe.objects.create(name="Mining", slug="mining", chief=chief)
        sync_tribe_chief_group_membership()
        chief_group = Group.objects.get(name=TRIBE_CHIEF_GROUP_NAME)
        self.assertIn(chief_group, chief.groups.all())

        tribe.chief = None
        tribe.save(update_fields=["chief"])
        sync_tribe_chief_group_membership()

        self.assertEqual(
            0, chief.groups.filter(name=TRIBE_CHIEF_GROUP_NAME).count()
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_excludes_inactive_tribe_chiefs(self):
        chief = User.objects.create_user(username="inactive_tribe_chief")
        Tribe.objects.create(
            name="Old",
            slug="old",
            chief=chief,
            is_active=False,
        )
        sync_tribe_chief_group_membership()

        self.assertEqual(
            0, chief.groups.filter(name=TRIBE_CHIEF_GROUP_NAME).count()
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_adds_active_tribe_group_chief(self):
        tribe_chief = User.objects.create_user(username="tribe_chief_tg")
        group_chief = User.objects.create_user(
            username="tribe_group_chief_sync"
        )
        tribe = Tribe.objects.create(
            name="Capitals",
            slug="capitals",
            chief=tribe_chief,
        )
        TribeGroup.objects.create(
            tribe=tribe, name="Dreads", chief=group_chief
        )
        sync_tribe_chief_group_membership()
        chief_group = Group.objects.get(name=TRIBE_CHIEF_GROUP_NAME)
        self.assertIn(chief_group, group_chief.groups.all())
        self.assertIn(chief_group, tribe_chief.groups.all())

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_removes_when_tribe_group_chief_cleared(self):
        group_chief = User.objects.create_user(username="former_group_chief")
        tribe = Tribe.objects.create(name="Capitals", slug="capitals2")
        tg = TribeGroup.objects.create(
            tribe=tribe, name="Carriers", chief=group_chief
        )
        sync_tribe_chief_group_membership()
        chief_group = Group.objects.get(name=TRIBE_CHIEF_GROUP_NAME)
        self.assertIn(chief_group, group_chief.groups.all())

        tg.chief = None
        tg.save(update_fields=["chief"])
        sync_tribe_chief_group_membership()

        self.assertEqual(
            0, group_chief.groups.filter(name=TRIBE_CHIEF_GROUP_NAME).count()
        )
