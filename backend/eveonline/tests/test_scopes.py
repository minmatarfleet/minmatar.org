from esi.models import Scope, Token

from app.test import TestCase
from eveonline.scopes import (
    BASIC_SCOPES,
    DIRECTOR_SCOPES,
    INDUSTRY_SCOPES,
    NOT_GATED_SCOPES,
    TokenType,
    scope_group,
    scope_groups,
    scopes_for,
    token_satisfies_type,
)


def token_with(scopes) -> Token:
    token = Token.objects.create(character_id=1)
    for name in scopes:
        token.scopes.add(Scope.objects.get_or_create(name=name)[0])
    return token


BASIC_BEFORE = set(BASIC_SCOPES) - NOT_GATED_SCOPES["Basic"]
DIRECTOR_BEFORE = set(DIRECTOR_SCOPES) - NOT_GATED_SCOPES["Director"]


class ScopesAddedLaterTestCase(TestCase):
    def test_tokens_granted_before_still_pass_gates(self):
        industry = token_with(BASIC_BEFORE | set(INDUSTRY_SCOPES))
        self.assertTrue(token_satisfies_type(industry, TokenType.BASIC))
        self.assertTrue(token_satisfies_type(industry, TokenType.INDUSTRY))
        self.assertEqual(["Industry"], scope_groups(industry))

        director = token_with(BASIC_BEFORE | DIRECTOR_BEFORE)
        self.assertTrue(token_satisfies_type(director, TokenType.DIRECTOR))

    def test_a_scope_another_group_lists_stays_gated(self):
        # Corporation contracts are new to Director but always were Market.
        contracts = "esi-contracts.read_corporation_contracts.v1"
        market = token_with(set(scopes_for(TokenType.MARKET)) - {contracts})
        self.assertFalse(token_satisfies_type(market, TokenType.MARKET))

    def test_a_full_director_token_reads_as_director(self):
        director = token_with(scopes_for(TokenType.DIRECTOR))
        self.assertEqual("Director", scope_group(director))
        self.assertNotIn("Market", scope_groups(director))

    def test_executor_names_each_scope_once(self):
        scopes = scopes_for(TokenType.EXECUTOR)
        self.assertEqual(len(scopes), len(set(scopes)))
        self.assertIn("esi-mail.send_mail.v1", scopes)
