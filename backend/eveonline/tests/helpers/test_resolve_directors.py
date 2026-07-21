"""Tests for director/CEO token resolution used by corporation ESI syncs."""

import factory
from django.db.models import signals
from esi.models import Scope, Token

from app.test import TestCase
from eveonline.helpers.corporations.update import (
    SCOPE_CORPORATION_CONTRACTS,
    resolve_directors_by_scope,
)
from eveonline.models import EveCharacter, EveCorporation

CORP_ID = 98705678
OTHER_CORP_ID = 98838663


def _character_with_scopes(character_id, corporation_id, scopes):
    token = Token.objects.create(character_id=character_id)
    for scope_name in scopes:
        scope, _ = Scope.objects.get_or_create(name=scope_name)
        token.scopes.add(scope)
    return EveCharacter.objects.create(
        character_id=character_id,
        corporation_id=corporation_id,
        token=token,
    )


class ResolveDirectorsByScopeTestCase(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_skips_directors_no_longer_in_corporation(self):
        corporation = EveCorporation.objects.create(corporation_id=CORP_ID)
        stale_director = _character_with_scopes(
            96129158, OTHER_CORP_ID, SCOPE_CORPORATION_CONTRACTS
        )
        ceo = _character_with_scopes(
            149027055, CORP_ID, SCOPE_CORPORATION_CONTRACTS
        )
        corporation.ceo = ceo
        corporation.save()
        corporation.directors.add(stale_director)

        results = resolve_directors_by_scope(
            corporation, [SCOPE_CORPORATION_CONTRACTS]
        )

        self.assertEqual(ceo, results[tuple(SCOPE_CORPORATION_CONTRACTS)])

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_returns_none_when_only_candidates_left_corporation(self):
        corporation = EveCorporation.objects.create(corporation_id=CORP_ID)
        stale_director = _character_with_scopes(
            96129158, OTHER_CORP_ID, SCOPE_CORPORATION_CONTRACTS
        )
        corporation.directors.add(stale_director)

        results = resolve_directors_by_scope(
            corporation, [SCOPE_CORPORATION_CONTRACTS]
        )

        self.assertIsNone(results[tuple(SCOPE_CORPORATION_CONTRACTS)])

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_allows_candidate_with_unknown_affiliation(self):
        corporation = EveCorporation.objects.create(corporation_id=CORP_ID)
        director = _character_with_scopes(
            90000001, None, SCOPE_CORPORATION_CONTRACTS
        )
        corporation.directors.add(director)

        results = resolve_directors_by_scope(
            corporation, [SCOPE_CORPORATION_CONTRACTS]
        )

        self.assertEqual(director, results[tuple(SCOPE_CORPORATION_CONTRACTS)])
