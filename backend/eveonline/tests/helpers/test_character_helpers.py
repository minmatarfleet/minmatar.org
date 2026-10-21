import factory

from django.db.models import signals
from esi.models import Scope, Token

from app.test import TestCase

from eveonline.helpers.characters import (
    character_configured_scope_groups,
    character_desired_scopes,
    merge_scope_groups,
    related_characters,
    scope_groups_for_token_add,
    scope_groups_granted,
    scopes_for_token_add,
)
from eveonline.models import EveCharacter
from eveonline.scopes import (
    DESKTOP_SCOPES,
    TokenType,
    parse_scope_groups,
    scope_group,
    scope_groups,
    scope_names,
    scopes_for,
    scopes_for_groups,
    add_scopes,
    token_satisfies_type,
)


class CharacterHelperTests(TestCase):
    """Unit tests for character helpers"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_character_desired_scopes(self):
        char = EveCharacter.objects.create(
            character_id=10001,
            character_name="Test Pilot",
            esi_token_level="Basic",
        )
        char.token = Token.objects.create(
            user=self.user,
            character_id=char.character_id,
        )
        char.save()

        self.assertEqual(11, len(character_desired_scopes(char)))

        self.assertEqual(0, len(scope_names(char.token)))

        add_scopes(TokenType.DIRECTOR, char.token)

        self.assertEqual(29, len(scope_names(char.token)))

        self.assertEqual(35, len(scopes_for(TokenType.EXECUTOR)))

    def test_merge_scope_groups(self):
        self.assertEqual(
            ["Basic", "Industry"],
            merge_scope_groups(["Basic"], "Industry"),
        )
        self.assertEqual(
            ["Basic", "Director"],
            merge_scope_groups(["Basic"], "CEO"),
        )

    def test_character_configured_scope_groups(self):
        char = EveCharacter.objects.create(
            character_id=10002,
            character_name="Director Alt",
            esi_token_level="Director",
            esi_scope_groups=["Basic"],
        )
        self.assertEqual(
            ["Basic", "Director"],
            character_configured_scope_groups(char),
        )

    def test_token_satisfies_type(self):
        char = EveCharacter.objects.create(
            character_id=10003,
            character_name="Industry Alt",
        )
        token = Token.objects.create(
            user=self.user,
            character_id=char.character_id,
        )
        add_scopes(TokenType.INDUSTRY, token)
        self.assertTrue(token_satisfies_type(token, TokenType.INDUSTRY))
        self.assertFalse(token_satisfies_type(token, TokenType.DIRECTOR))

    def test_scope_groups_for_token_add(self):
        char = EveCharacter.objects.create(
            character_id=10004,
            character_name="Director Alt",
            esi_token_level="Director",
            esi_scope_groups=["Basic"],
        )
        self.assertEqual(
            ["Basic", "Director", "Industry"],
            scope_groups_for_token_add(char, TokenType.INDUSTRY),
        )
        self.assertEqual(
            len(scopes_for_groups(["Basic", "Director", "Industry"])),
            len(
                set(scopes_for(TokenType.DIRECTOR))
                | set(scopes_for(TokenType.INDUSTRY))
            ),
        )

    def test_new_character_add_requests_faction_warfare(self):
        self.assertEqual(
            ["Basic", "FactionWarfare"],
            scope_groups_for_token_add(None, TokenType.BASIC),
        )
        scopes = scopes_for_token_add(None, TokenType.BASIC)
        self.assertIn("esi-characters.read_fw_stats.v1", scopes)
        self.assertIn("esi-characters.read_notifications.v1", scopes)

    def test_guest_add_does_not_request_faction_warfare(self):
        self.assertEqual(
            ["Public"], scope_groups_for_token_add(None, TokenType.PUBLIC)
        )

    def test_existing_character_add_does_not_widen(self):
        char = EveCharacter.objects.create(
            character_id=10006,
            character_name="Basic Alt",
            esi_token_level="Basic",
            esi_scope_groups=["Basic"],
        )
        self.assertEqual(
            ["Basic"], scope_groups_for_token_add(char, TokenType.BASIC)
        )

    def test_token_granted_before_the_split_still_satisfies_basic(self):
        token = Token.objects.create(user=self.user, character_id=10007)
        add_scopes(TokenType.BASIC, token)
        fw_stats, _ = Scope.objects.get_or_create(
            name="esi-characters.read_fw_stats.v1"
        )
        token.scopes.add(fw_stats)

        self.assertTrue(token_satisfies_type(token, TokenType.BASIC))
        self.assertFalse(
            token_satisfies_type(token, TokenType.FACTION_WARFARE)
        )
        self.assertEqual("Basic", scope_group(token))

    def test_scope_groups_lists_every_group_widest_first(self):
        token = Token.objects.create(user=self.user, character_id=10010)
        for token_type in (
            TokenType.EXECUTOR,
            TokenType.INDUSTRY,
            TokenType.FLEET_COMMANDER,
            TokenType.FACTION_WARFARE,
            TokenType.DESKTOP,
        ):
            add_scopes(token_type, token)

        self.assertEqual(
            [
                "Executor",
                "Market",
                "Director",
                "Industry",
                "FleetCommander",
                "FactionWarfare",
                "Desktop",
            ],
            scope_groups(token),
        )

    def test_scope_groups_keeps_the_widest_label_on_a_partial_token(self):
        token = Token.objects.create(user=self.user, character_id=10011)
        add_scopes(TokenType.BASIC, token)
        blueprints, _ = Scope.objects.get_or_create(
            name="esi-characters.read_blueprints.v1"
        )
        token.scopes.add(blueprints)

        self.assertEqual(["Industry"], scope_groups(token))

    def test_scope_groups_basic_token(self):
        token = Token.objects.create(user=self.user, character_id=10012)
        add_scopes(TokenType.BASIC, token)

        self.assertEqual(["Basic"], scope_groups(token))

    def test_market_does_not_request_director_scopes(self):
        market = set(scopes_for(TokenType.MARKET))
        self.assertEqual(16, len(market))
        self.assertNotIn(
            "esi-corporations.read_corporation_membership.v1", market
        )
        self.assertIn("esi-markets.structure_markets.v1", market)

    def test_token_granted_before_the_market_trim_still_satisfies_both(self):
        token = Token.objects.create(user=self.user, character_id=10009)
        add_scopes(TokenType.BASIC, token)
        add_scopes(TokenType.DIRECTOR, token)
        add_scopes(TokenType.MARKET, token)

        self.assertTrue(token_satisfies_type(token, TokenType.MARKET))
        self.assertTrue(token_satisfies_type(token, TokenType.DIRECTOR))

    def test_parse_scope_groups_keeps_selectable_groups_once(self):
        self.assertEqual(
            [TokenType.INDUSTRY, TokenType.MARKET, TokenType.DIRECTOR],
            parse_scope_groups("Industry, Market,Industry,Director"),
        )
        self.assertEqual([], parse_scope_groups("Executor,Public,Basic,Nope"))
        self.assertEqual([], parse_scope_groups(None))

    def test_new_character_add_requests_picked_groups(self):
        self.assertEqual(
            ["Basic", "Industry", "Director", "FactionWarfare"],
            scope_groups_for_token_add(
                None,
                TokenType.BASIC,
                [TokenType.INDUSTRY, TokenType.DIRECTOR],
            ),
        )
        scopes = scopes_for_token_add(
            None, TokenType.BASIC, [TokenType.MARKET]
        )
        self.assertIn("esi-markets.structure_markets.v1", scopes)
        self.assertNotIn(
            "esi-corporations.read_corporation_membership.v1", scopes
        )

    def test_scope_groups_granted_records_picked_groups_the_token_holds(self):
        token = Token.objects.create(user=self.user, character_id=10010)
        add_scopes(TokenType.BASIC, token)
        add_scopes(TokenType.FACTION_WARFARE, token)
        add_scopes(TokenType.INDUSTRY, token)

        self.assertEqual(
            ["Basic", "Industry", "FactionWarfare"],
            scope_groups_granted(
                token,
                TokenType.BASIC,
                [TokenType.INDUSTRY, TokenType.MARKET],
            ),
        )

    def test_campaign_is_a_legacy_name_for_faction_warfare(self):
        self.assertEqual(
            scopes_for(TokenType.FACTION_WARFARE),
            scopes_for(TokenType.CAMPAIGN),
        )
        self.assertEqual(
            ["Basic", "FactionWarfare"],
            merge_scope_groups(["Basic"], "Campaign"),
        )

    def test_scope_groups_granted_reads_faction_warfare_off_the_token(self):
        token = Token.objects.create(user=self.user, character_id=10008)
        add_scopes(TokenType.BASIC, token)
        self.assertEqual(
            ["Basic"], scope_groups_granted(token, TokenType.BASIC)
        )

        add_scopes(TokenType.FACTION_WARFARE, token)
        self.assertEqual(
            ["Basic", "FactionWarfare"],
            scope_groups_granted(token, TokenType.BASIC),
        )
        self.assertEqual("FactionWarfare", scope_group(token))

    def test_desktop_group_is_picked_recorded_and_labelled(self):
        self.assertEqual(
            [TokenType.DESKTOP], parse_scope_groups("Desktop,Desktop")
        )

        token = Token.objects.create(user=self.user, character_id=10011)
        add_scopes(TokenType.BASIC, token)
        add_scopes(TokenType.DESKTOP, token)
        self.assertEqual("Desktop", scope_group(token))
        self.assertEqual(
            ["Basic", "Desktop"],
            scope_groups_granted(token, TokenType.BASIC, [TokenType.DESKTOP]),
        )

        # New characters get Faction Warfare too; that label wins.
        add_scopes(TokenType.FACTION_WARFARE, token)
        self.assertEqual("FactionWarfare", scope_group(token))

    def test_desktop_scopes_overlap_no_other_group(self):
        desktop = set(DESKTOP_SCOPES)
        for token_type in TokenType:
            if token_type in (TokenType.DESKTOP, TokenType.PUBLIC):
                continue
            self.assertFalse(
                desktop & set(scopes_for(token_type)), token_type.value
            )

    def test_scopes_for_token_add_keeps_scopes_already_granted(self):
        char = EveCharacter.objects.create(
            character_id=10005,
            character_name="Wide Token",
            esi_token_level="Executor",
            esi_scope_groups=["Executor"],
        )
        token = Token.objects.create(
            user=self.user,
            character_id=char.character_id,
            character_name=char.character_name,
        )
        char.token = token
        char.save()
        add_scopes(TokenType.EXECUTOR, token)
        extra, _ = Scope.objects.get_or_create(name="esi-custom.extra.v1")
        token.scopes.add(extra)

        scopes = scopes_for_token_add(char, TokenType.FACTION_WARFARE)

        self.assertIn("esi-characters.read_notifications.v1", scopes)
        self.assertIn("esi-custom.extra.v1", scopes)
        self.assertGreaterEqual(len(scopes), token.scopes.count())

    def test_related_characters_returns_same_user_characters(self):
        """related_characters returns all characters for the given character's user."""
        char_a = EveCharacter.objects.create(
            character_id=20001,
            character_name="Alpha",
            user=self.user,
        )
        EveCharacter.objects.create(
            character_id=20002,
            character_name="Beta",
            user=self.user,
        )
        related = related_characters(char_a)
        self.assertEqual(len(related), 2)
        self.assertCountEqual(
            [c.character_id for c in related], [20001, 20002]
        )
        self.assertEqual(
            [c.character_name for c in related], ["Alpha", "Beta"]
        )

    def test_related_characters_empty_when_no_user(self):
        """related_characters returns empty list when character has no user."""
        char = EveCharacter.objects.create(
            character_id=20003,
            character_name="Orphan",
            user=None,
        )
        self.assertEqual(related_characters(char), [])

    def test_related_characters_none_returns_empty(self):
        """related_characters returns empty list when passed None."""
        self.assertEqual(related_characters(None), [])
