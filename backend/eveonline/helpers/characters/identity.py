"""Who owns a character, and which character is a user's main.

Ownership rule (use these helpers instead of re-deriving it):

* ``EveCharacter.user`` is authoritative. Add-character sets it to the
  website user who finished SSO (``owner_for_added_character``), not to
  whoever django-esi stored on the token. Re-adding the character from a
  different account moves it: ``apply_token_to_existing_character`` swaps
  the token and sets ``character.user`` to the new owner.
  ``orphan_character`` clears the user and deletes the tokens together.
* ``Token.user`` is what django-esi recorded at SSO time. Nothing keeps it
  in step with a transfer (only mobile login re-syncs it, and only when
  ``character.user`` is already set), so it can be stale. It is used only
  for a character that has no ``user`` at all: legacy rows linked through
  their token alone. It never overrides a set ``character.user``.

So the owner of a character is ``Coalesce(character.user, token.user)``.

A user's main is ``EvePlayer.primary_character`` (both ends of EvePlayer
are one-to-one, so a user has at most one main).
"""

from collections import defaultdict
from typing import Iterable

from django.contrib.auth.models import User
from django.db.models import F, Q
from django.db.models.functions import Coalesce

from eveonline.models import EveCharacter, EvePlayer


def _ids(values: Iterable[int | None]) -> set[int]:
    return {int(value) for value in values if value}


def owned_by_q(user_ids: int | Iterable[int], prefix: str = "") -> Q:
    """Filter characters owned by one user id or any of several.

    ``prefix`` reaches a character through a relation, e.g.
    ``owned_by_q(user.id, "ceo__")`` on EveCorporation.
    """
    if isinstance(user_ids, int):
        ids = [user_ids]
    else:
        ids = sorted(_ids(user_ids))
    return Q(**{f"{prefix}user_id__in": ids}) | Q(
        **{
            f"{prefix}user__isnull": True,
            f"{prefix}token__user_id__in": ids,
        }
    )


def owner_user_ids(character_ids: Iterable[int]) -> dict[int, int]:
    """EVE character id -> owning user id, in one query.

    Characters nobody owns are left out.
    """
    ids = _ids(character_ids)
    if not ids:
        return {}
    return dict(
        EveCharacter.objects.filter(character_id__in=ids)
        .annotate(owner_id=Coalesce(F("user_id"), F("token__user_id")))
        .filter(owner_id__isnull=False)
        .values_list("character_id", "owner_id")
    )


def owner_users_for_characters(
    character_ids: Iterable[int],
) -> dict[int, int]:
    """Alias of :func:`owner_user_ids`."""
    return owner_user_ids(character_ids)


def character_ids_for_users(user_ids: Iterable[int]) -> dict[int, int]:
    """EVE character id -> user id for every character the users own."""
    ids = _ids(user_ids)
    if not ids:
        return {}
    return {
        character_id: owner_id
        for character_id, owner_id in EveCharacter.objects.filter(
            owned_by_q(ids)
        )
        .annotate(owner_id=Coalesce(F("user_id"), F("token__user_id")))
        .values_list("character_id", "owner_id")
        if character_id
    }


def characters_by_user(user_ids: Iterable[int]) -> dict[int, set[int]]:
    """User id -> EVE character ids they own."""
    out: dict[int, set[int]] = defaultdict(set)
    for character_id, user_id in character_ids_for_users(user_ids).items():
        out[user_id].add(character_id)
    return dict(out)


def primary_characters_for_users(
    user_ids: Iterable[int],
) -> dict[int, EveCharacter]:
    """User id -> main EveCharacter, in one query. Users without one are
    left out."""
    ids = _ids(user_ids)
    if not ids:
        return {}
    return {
        player.user_id: player.primary_character
        for player in EvePlayer.objects.filter(
            user_id__in=ids, primary_character__isnull=False
        ).select_related("primary_character")
    }


def primary_refs_for_users(
    user_ids: Iterable[int],
) -> dict[int, tuple[int, str]]:
    """User id -> (main's EVE character id, name)."""
    return {
        user_id: (int(main.character_id), main.character_name or "")
        for user_id, main in primary_characters_for_users(user_ids).items()
    }


def primary_characters_for_characters(
    character_ids: Iterable[int],
) -> dict[int, EveCharacter]:
    """EVE character id -> its owner's main, in two queries. Characters
    with no owner, or whose owner has no main, are left out."""
    owners = owner_user_ids(character_ids)
    mains = primary_characters_for_users(owners.values())
    return {
        character_id: mains[user_id]
        for character_id, user_id in owners.items()
        if user_id in mains
    }


def primary_character_for_user(user: User | None) -> EveCharacter | None:
    """The user's main, in one query. Always reads the database: a list
    endpoint should batch with :func:`primary_characters_for_users`
    instead of calling this per row."""
    if user is None or not getattr(user, "pk", None):
        return None
    player = (
        EvePlayer.objects.filter(user_id=user.pk)
        .select_related("primary_character")
        .first()
    )
    return player.primary_character if player else None
