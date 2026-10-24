"""Ownership and main-character lookups: one rule, batch queries."""

from django.contrib.auth.models import User
from django.test import TestCase
from esi.models import Token

from eveonline.helpers.characters import (
    character_primary,
    set_primary_character,
    user_primary_character,
)
from eveonline.helpers.characters.identity import (
    character_ids_for_users,
    characters_by_user,
    owned_by_q,
    owner_user_ids,
    owner_users_for_characters,
    primary_characters_for_characters,
    primary_characters_for_users,
    primary_refs_for_users,
)
from eveonline.models import EveCharacter


class OwnershipFixture(TestCase):
    """alice: main 1, alt 2, legacy token-only alt 3.
    bob: main 10; character 11 is bob's but its token still names alice
    (moved accounts). nobody: 20 (no user, no token), 21 (token, no user).
    carol: user with no EvePlayer; character 30."""

    def setUp(self):
        self.alice = User.objects.create(username="alice")
        self.bob = User.objects.create(username="bob")
        self.carol = User.objects.create(username="carol")

        def char(cid, user=None, token_user=None, has_token=False):
            token = None
            if token_user is not None or has_token:
                token = Token.objects.create(character_id=cid, user=token_user)
            return EveCharacter.objects.create(
                character_id=cid,
                character_name=f"c{cid}",
                user=user,
                token=token,
            )

        self.a_main = char(1, user=self.alice, token_user=self.alice)
        char(2, user=self.alice)
        char(3, token_user=self.alice)
        self.b_main = char(10, user=self.bob)
        char(11, user=self.bob, token_user=self.alice)
        char(20)
        char(21, has_token=True)
        char(30, user=self.carol)
        set_primary_character(self.alice, self.a_main)
        set_primary_character(self.bob, self.b_main)


class OwnerUserIdsTest(OwnershipFixture):
    def test_character_user_wins_and_token_only_counts(self):
        with self.assertNumQueries(1):
            owners = owner_user_ids([1, 2, 3, 10, 11, 20, 21, 30, 999])
        self.assertEqual(
            owners,
            {
                1: self.alice.id,
                2: self.alice.id,
                3: self.alice.id,  # legacy token-only link
                10: self.bob.id,
                11: self.bob.id,  # stale token.user ignored
                30: self.carol.id,
            },
        )
        self.assertEqual(owner_users_for_characters([11]), {11: self.bob.id})

    def test_empty_input_runs_no_query(self):
        with self.assertNumQueries(0):
            self.assertEqual(owner_user_ids([]), {})
            self.assertEqual(owner_user_ids([None, 0]), {})
            self.assertEqual(primary_characters_for_users([]), {})

    def test_characters_for_users_uses_same_rule(self):
        self.assertEqual(
            character_ids_for_users([self.alice.id]),
            {1: self.alice.id, 2: self.alice.id, 3: self.alice.id},
        )
        self.assertEqual(
            characters_by_user([self.alice.id, self.bob.id]),
            {self.alice.id: {1, 2, 3}, self.bob.id: {10, 11}},
        )
        self.assertEqual(
            set(
                EveCharacter.objects.filter(
                    owned_by_q(self.alice.id)
                ).values_list("character_id", flat=True)
            ),
            {1, 2, 3},
        )


class PrimaryLookupTest(OwnershipFixture):
    def test_primary_for_users_one_query(self):
        with self.assertNumQueries(1):
            mains = primary_characters_for_users(
                [self.alice.id, self.bob.id, self.carol.id]
            )
            names = {uid: c.character_name for uid, c in mains.items()}
        self.assertEqual(names, {self.alice.id: "c1", self.bob.id: "c10"})
        self.assertEqual(
            primary_refs_for_users([self.alice.id]), {self.alice.id: (1, "c1")}
        )

    def test_primary_for_characters_matches_character_primary(self):
        ids = [1, 2, 3, 10, 11, 20, 21, 30]
        with self.assertNumQueries(2):
            batch = primary_characters_for_characters(ids)
        for cid in ids:
            single = character_primary(
                EveCharacter.objects.get(character_id=cid)
            )
            expected = single.character_id if single else None
            got = batch[cid].character_id if cid in batch else None
            self.assertEqual(got, expected, cid)

    def test_character_primary_without_user_or_token_is_none(self):
        # Used to raise AttributeError on character.token.user.
        self.assertIsNone(
            character_primary(EveCharacter.objects.get(character_id=20))
        )
        self.assertIsNone(
            character_primary(EveCharacter.objects.get(character_id=21))
        )

    def test_user_primary_character_is_one_fresh_query(self):
        with self.assertNumQueries(1):
            self.assertEqual(user_primary_character(self.alice), self.a_main)

    def test_user_primary_character_without_player(self):
        self.assertIsNone(user_primary_character(self.carol))
        self.assertIsNone(user_primary_character(User()))

    def test_user_primary_character_never_reads_a_stale_loaded_player(self):
        # A user object that loaded (or created) its EvePlayer earlier must
        # still see a main changed through another object.
        user = User.objects.select_related("eveplayer").get(pk=self.alice.pk)
        self.assertEqual(user.eveplayer.primary_character_id, self.a_main.pk)
        other = User.objects.get(pk=self.alice.pk)
        set_primary_character(other, EveCharacter.objects.get(character_id=2))
        self.assertEqual(user_primary_character(user).character_id, 2)
