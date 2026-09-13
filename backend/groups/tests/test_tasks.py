from unittest.mock import patch

import factory

from django.contrib.auth.models import Group, User
from django.db import IntegrityError
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
    _ensure_user_affiliation,
    update_affiliation,
    update_affiliations,
    sync_eve_corporation_groups,
    sync_user_corporation_groups,
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

        # qualify by specific character
        affiliation_type.characters.add(character)
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        affiliation_type.characters.remove(character)
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

    def test_set_user_affiliation_replaces_lower_priority(self):
        user = User.objects.create(
            username="test_set_user_affiliation_replaces_lower_priority"
        )
        group = Group.objects.create(
            name="test_set_user_affiliation_replaces_lower_priority"
        )
        group_2 = Group.objects.create(
            name="test_set_user_affiliation_replaces_lower_priority_2"
        )
        corporation = EveCorporation.objects.create(corporation_id=98726135)
        character = EveCharacter.objects.create(character_id=124)
        token = Token.objects.create(
            character_id=124,
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
        character.corporation_id = corporation.corporation_id
        character.save()
        update_affiliations()
        self.assertEqual(
            UserAffiliation.objects.get(user=user).affiliation,
            affiliation_type,
        )

        affiliation_type_2.corporations.add(corporation)
        update_affiliations()
        self.assertEqual(UserAffiliation.objects.filter(user=user).count(), 1)
        self.assertEqual(
            UserAffiliation.objects.get(user=user).affiliation,
            affiliation_type_2,
        )

    def test_ensure_user_affiliation_swallows_integrity_error(self):
        user = User.objects.create(
            username="test_ensure_user_affiliation_integrity"
        )
        group = Group.objects.create(
            name="test_ensure_user_affiliation_integrity"
        )
        affiliation = AffiliationType.objects.create(
            name="Example",
            description="Example",
            image_url="https://example.com/image.png",
            group=group,
            priority=1,
        )
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        with patch(
            "groups.tasks.UserAffiliation.objects.get_or_create",
            side_effect=IntegrityError(),
        ):
            _ensure_user_affiliation(user, affiliation)
        self.assertEqual(UserAffiliation.objects.filter(user=user).count(), 1)

    def test_update_affiliation_logs_errors_instead_of_raising(self):
        with patch(
            "groups.tasks._update_affiliation_for_user",
            side_effect=RuntimeError("boom"),
        ):
            update_affiliation(self.user.id)
        self.assertFalse(
            UserAffiliation.objects.filter(user=self.user).exists()
        )


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

        other_corp = EveCorporation.objects.create(
            corporation_id=100002,
            name="OtherCorp",
        )
        EveCorporationGroup.objects.create(
            corporation=other_corp,
            group=Group.objects.create(name=f"{other_corp.name} group"),
        )
        other_user = User.objects.create_user(username="other_corp_user")
        other_char = EveCharacter.objects.create(
            character_id=1002,
            character_name="Other Pilot",
            corporation_id=other_corp.corporation_id,
        )
        set_primary_character(other_user, other_char)

        sync_eve_corporation_groups()

        self.assertEqual(1, self.user.groups.count())
        self.assertEqual(1, other_user.groups.count())
        self.assertEqual(
            f"{other_corp.name} group", other_user.groups.all()[0].name
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_eve_corporation_groups_any_linked_character(self):
        corp_a = EveCorporation.objects.create(
            corporation_id=100011,
            name="CorpAlpha",
        )
        corp_b = EveCorporation.objects.create(
            corporation_id=100012,
            name="CorpBeta",
        )
        group_a = Group.objects.create(name=f"{corp_a.name} group")
        group_b = Group.objects.create(name=f"{corp_b.name} group")
        EveCorporationGroup.objects.create(corporation=corp_a, group=group_a)
        EveCorporationGroup.objects.create(corporation=corp_b, group=group_b)

        primary = EveCharacter.objects.create(
            character_id=1011,
            character_name="Primary Pilot",
            corporation_id=corp_a.corporation_id,
        )
        set_primary_character(self.user, primary)
        EveCharacter.objects.create(
            character_id=1012,
            character_name="Alt Pilot",
            corporation_id=corp_b.corporation_id,
            user=self.user,
        )

        sync_eve_corporation_groups()

        self.assertEqual(
            {group_a.name, group_b.name},
            set(self.user.groups.values_list("name", flat=True)),
        )

        alt = EveCharacter.objects.get(character_id=1012)
        alt.corporation_id = None
        alt.save(update_fields=["corporation_id"])

        sync_eve_corporation_groups()

        self.assertEqual(
            [group_a.name],
            list(self.user.groups.values_list("name", flat=True)),
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_user_corporation_groups_switches_corp(self):
        old_corp = EveCorporation.objects.create(
            corporation_id=98838034,
            name="FOSFO",
        )
        new_corp = EveCorporation.objects.create(
            corporation_id=98741376,
            name="L3ARN",
        )
        old_group = Group.objects.create(name="Corp FOSFO")
        new_group = Group.objects.create(name="Corp L3ARN")
        EveCorporationGroup.objects.create(
            corporation=old_corp, group=old_group
        )
        EveCorporationGroup.objects.create(
            corporation=new_corp, group=new_group
        )
        char = EveCharacter.objects.create(
            character_id=2115133763,
            character_name="Paul Steinor",
            corporation_id=old_corp.corporation_id,
        )
        set_primary_character(self.user, char)
        self.user.groups.add(old_group)

        char.corporation_id = new_corp.corporation_id
        char.save(update_fields=["corporation_id"])
        sync_user_corporation_groups(self.user)

        self.assertEqual(
            [new_group.name],
            list(self.user.groups.values_list("name", flat=True)),
        )


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
