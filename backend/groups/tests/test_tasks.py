from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client
from esi.models import Token
from eveuniverse.models import EveFaction

from app.test import TestCase
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePrimaryCharacter,
)
from groups.models import AffiliationType, UserAffiliation
from groups.tasks import update_affiliations


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
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
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
        faction = EveFaction.objects.get_or_create_esi(id=500002)[0]
        character = EveCharacter.objects.create(character_id=123)
        token = Token.objects.create(
            character_id=123,
            user=user,
        )
        character.token = token
        character.save()
        EvePrimaryCharacter.objects.create(
            character=character,
        )
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
        character.corporation = corporation
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.corporation = None
        character.save()
        user_affiliation.delete()

        # qualify by alliance
        character.alliance = alliance
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.alliance = None
        character.save()
        user_affiliation.delete()

        # qualify by faction
        character.faction = faction
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.faction = None
        character.save()
        user_affiliation.delete()

        # remove if not qualified
        character.faction = faction
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type
        character.faction = None
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
        EvePrimaryCharacter.objects.create(
            character=character,
        )
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
        character.corporation = corporation
        character.save()
        update_affiliations()
        user_affiliation = UserAffiliation.objects.get(user=user)
        assert user_affiliation.affiliation == affiliation_type_2
