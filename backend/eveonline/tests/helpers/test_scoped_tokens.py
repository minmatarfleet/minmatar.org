"""One query to find characters holding ESI scopes, matching
Token.get_token for every character."""

from contextlib import ExitStack

import factory
from django.db.models import signals
from django.test import TestCase
from esi.models import Scope, Token

from eveonline.helpers.characters.tokens import (
    character_ids_with_scopes,
    first_character_with_scopes,
)
from eveonline.helpers.corporations.update import resolve_directors_by_scope
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from market.helpers.contract_fetch import (
    STRUCTURE_MARKET_SCOPES,
    get_character_with_structure_markets_scope,
)

MARKETS = STRUCTURE_MARKET_SCOPES[0]
CONTRACTS = "esi-contracts.read_corporation_contracts.v1"
ALLIANCE_ID = 99011978
CORP_ID = 98000001


def _token(character_id, scopes):
    token = Token.objects.create(character_id=character_id)
    for name in scopes:
        scope, _ = Scope.objects.get_or_create(name=name)
        token.scopes.add(scope)
    return token


class ScopedTokenTest(TestCase):
    def setUp(self):
        stack = ExitStack()
        stack.enter_context(
            factory.django.mute_signals(signals.pre_save, signals.post_save)
        )
        self.addCleanup(stack.close)
        Scope.objects.get_or_create(name=MARKETS)
        Scope.objects.get_or_create(name=CONTRACTS)
        EveAlliance.objects.create(alliance_id=ALLIANCE_ID, name="A")
        # 1: no token. 2: token without the scope. 3: suspended holder.
        # 4: holder. 5: holder with both scopes. 6: extra token row only.
        specs = [
            (1, None, False),
            (2, [CONTRACTS], False),
            (3, [MARKETS], True),
            (4, [MARKETS], False),
            (5, [MARKETS, CONTRACTS], False),
        ]
        for cid, scopes, suspended in specs:
            EveCharacter.objects.create(
                character_id=cid,
                character_name=f"c{cid}",
                alliance_id=ALLIANCE_ID,
                corporation_id=CORP_ID,
                esi_suspended=suspended,
                token=_token(cid, scopes) if scopes else None,
            )
        EveCharacter.objects.create(
            character_id=6,
            alliance_id=ALLIANCE_ID,
            corporation_id=CORP_ID,
            token=_token(6, [CONTRACTS]),
        )
        _token(6, [MARKETS])  # second, unlinked token row

    def test_matches_get_token_for_each_character(self):
        ids = [1, 2, 3, 4, 5, 6, 404]
        for scopes in ([MARKETS], [CONTRACTS], [MARKETS, CONTRACTS]):
            expected = {cid for cid in ids if Token.get_token(cid, scopes)}
            self.assertEqual(character_ids_with_scopes(ids, scopes), expected)
        self.assertEqual(character_ids_with_scopes([], [MARKETS]), set())
        self.assertEqual(
            character_ids_with_scopes(ids, ["esi-unknown.v1"]), set()
        )

    def test_first_follows_caller_order(self):
        self.assertEqual(first_character_with_scopes([5, 4], [MARKETS]), 5)
        self.assertEqual(first_character_with_scopes([1, 2], [MARKETS]), None)

    def test_structure_market_selector_one_lookup(self):
        old = None
        for character in (
            EveCharacter.objects.filter(alliance_id__in=[ALLIANCE_ID])
            .exclude(token__isnull=True)
            .exclude(esi_suspended=True)
            .order_by("pk")
        ):
            if Token.get_token(
                character.character_id, STRUCTURE_MARKET_SCOPES
            ):
                old = character.character_id
                break
        # alliance ids, candidates, scope pks + token lookup
        with self.assertNumQueries(4):
            new = get_character_with_structure_markets_scope()
        self.assertEqual(new, old)
        self.assertEqual(new, 4)

    def test_directors_pick_ceo_then_directors_per_scope(self):
        corp = EveCorporation.objects.create(corporation_id=CORP_ID)
        corp.ceo = EveCharacter.objects.get(character_id=2)
        corp.save()
        for cid in (1, 4, 5):
            corp.directors.add(EveCharacter.objects.get(character_id=cid))
        results = resolve_directors_by_scope(corp, [[CONTRACTS], [MARKETS]])
        self.assertEqual(results[(CONTRACTS,)].character_id, 2)
        self.assertEqual(results[(MARKETS,)].character_id, 4)
