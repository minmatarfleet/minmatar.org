"""Old resolvers vs the shared ownership service, on one fixture.

The old bodies are copied here verbatim (trimmed to the lookup) so a
refactor that drifts shows up as a diff. Where the old code ignored the
token-only ownership link, the only allowed difference is that link.
"""

# pylint: disable=protected-access

from django.contrib.auth.models import User
from django.test import TestCase
from esi.models import Token

from campaigns.services import stats as campaign_stats
from eveonline.helpers.characters import (
    character_primary,
    set_primary_character,
)
from eveonline.helpers.corporations import about as corp_about
from eveonline.helpers.corporations import profile as corp_profile
from eveonline.models import EveCharacter, EvePlayer
from freight.endpoints import get_contracts_stats
from industry.helpers import producers, product_insights
from tribes.reports.queries import common as tribe_common


def _old_primary_by_user(user_ids):
    return {
        p.user_id: (
            p.primary_character.character_id,
            p.primary_character.character_name or "",
        )
        for p in EvePlayer.objects.filter(
            user_id__in=[u for u in user_ids if u],
            primary_character__isnull=False,
        ).select_related("primary_character")
    }


def _old_token_aware_owner(char):
    """corp profile / freight / character_primary rule."""
    if char.user_id:
        return char.user_id
    if char.token_id and char.token.user_id:
        return char.token.user_id
    return None


class ParityFixture(TestCase):
    def setUp(self):
        self.alice = User.objects.create(username="alice")
        self.bob = User.objects.create(username="bob")
        self.carol = User.objects.create(username="carol")

        def char(cid, user=None, token_user=None, has_token=False, corp=1):
            token = None
            if token_user is not None or has_token:
                token = Token.objects.create(character_id=cid, user=token_user)
            return EveCharacter.objects.create(
                character_id=cid,
                character_name=f"c{cid}",
                user=user,
                token=token,
                corporation_id=corp,
            )

        a_main = char(1, user=self.alice, token_user=self.alice)
        char(2, user=self.alice)
        char(3, token_user=self.alice)  # legacy token-only link
        b_main = char(10, user=self.bob, corp=2)
        char(11, user=self.bob, token_user=self.alice)  # stale token user
        char(20)
        char(21, has_token=True)
        char(30, user=self.carol)
        set_primary_character(self.alice, a_main)
        set_primary_character(self.bob, b_main)
        self.ids = [1, 2, 3, 10, 11, 20, 21, 30, 404]
        self.chars = list(EveCharacter.objects.order_by("character_id"))


class SameRuleParityTest(ParityFixture):
    """Callers that already followed the token link: identical output."""

    def test_primary_characters_by_user(self):
        users = [self.alice.id, self.bob.id, self.carol.id, None]
        old = _old_primary_by_user(users)
        self.assertEqual(campaign_stats.primary_characters(users), old)
        self.assertEqual(tribe_common.primary_characters(users), old)

    def test_producers_merge_to_mains(self):
        refs = [
            {"id": cid, "name": f"c{cid}", "total_value_isk": 1.0}
            for cid in self.ids
        ]
        old_merged = {}
        for ref in refs:
            char = EveCharacter.objects.filter(character_id=ref["id"]).first()
            primary = character_primary(char) if char else None
            key = primary.character_id if primary else ref["id"]
            old_merged[key] = old_merged.get(key, 0) + 1.0
        new = producers._resolve_to_primary_producers(refs)
        self.assertEqual(
            {row["id"]: row["total_value_isk"] for row in new}, old_merged
        )
        self.assertEqual(old_merged[1], 3.0)  # 1, 2 and token-only 3
        self.assertEqual(old_merged[10], 2.0)  # 11's stale token ignored

    def test_corp_profile_leadership(self):
        entries = [(c, "Director") for c in self.chars]
        rows = corp_profile._collapse_leadership_to_mains(entries)
        old_users = {_old_token_aware_owner(c) for c in self.chars} - {None}
        self.assertEqual(
            {row["user_id"] for row in rows if row["user_id"]}, old_users
        )
        self.assertEqual(len(rows), 3 + 2)  # 3 people + 2 unowned

    def test_freight_hauler_count(self):
        old_keys = set()
        for cid in self.ids:
            char = EveCharacter.objects.filter(character_id=cid).first()
            owner = _old_token_aware_owner(char) if char else None
            old_keys.add(("user", owner) if owner else ("char", cid))
        owners = get_contracts_stats.owner_user_ids(self.ids)
        new_keys = {
            ("user", owners[cid]) if cid in owners else ("char", cid)
            for cid in self.ids
        }
        self.assertEqual(new_keys, old_keys)


class TokenLinkBehaviourChangeTest(ParityFixture):
    """Callers that used EveCharacter.user only now also follow a legacy
    token-only link (character 3). Everything else is unchanged."""

    def test_product_insights_primary_by_character(self):
        old_owner = {c.character_id: c.user_id for c in self.chars}
        old_mains = _old_primary_by_user(old_owner.values())
        old = {
            c.character_id: old_mains.get(c.user_id)
            or (c.character_id, c.character_name)
            for c in self.chars
        }
        new = product_insights._primary_by_character(self.ids)
        self.assertEqual(set(new), set(old))
        diff = {cid for cid in old if old[cid] != new[cid]}
        self.assertEqual(diff, {3})
        self.assertEqual(new[3], (1, "c1"))

    def test_corp_about_owners(self):
        old = {
            c.character_id: c.user_id or -c.character_id for c in self.chars
        }
        new = corp_about._owners(self.chars)
        diff = {cid for cid in old if old[cid] != new[cid]}
        self.assertEqual(diff, {3})
        self.assertEqual(new[3], self.alice.id)
        self.assertEqual(new[11], self.bob.id)
        mains = corp_about._mains(new)
        self.assertEqual(
            mains, {self.alice.id: (1, "c1"), self.bob.id: (10, "c10")}
        )

    def test_tribe_report_character_maps(self):
        old_to_users = {
            c.character_id: c.user_id for c in self.chars if c.user_id
        }
        new_to_users = tribe_common.characters_to_users(self.ids)
        self.assertEqual(
            {k: v for k, v in new_to_users.items() if k != 3}, old_to_users
        )
        self.assertEqual(new_to_users[3], self.alice.id)
        roster = tribe_common.roster_characters_by_eve_id([self.alice.id])
        self.assertEqual(set(roster), {1, 2, 3})
