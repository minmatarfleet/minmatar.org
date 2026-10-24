"""Pick characters that hold an ESI token with given scopes."""

from typing import Iterable, Sequence

from esi.models import Token


def character_ids_with_scopes(
    character_ids: Iterable[int], scopes: Sequence[str]
) -> set[int]:
    """The subset of ``character_ids`` with any stored token carrying every
    scope in ``scopes``, in one query.

    Same test as ``Token.get_token(character_id, scopes)`` (any token row
    for the character, not only ``EveCharacter.token``; no expiry check:
    ``EsiClient`` refreshes or suspends at use time).
    """
    ids = {int(cid) for cid in character_ids if cid}
    if not ids:
        return set()
    return set(
        Token.objects.filter(character_id__in=ids)
        .require_scopes(list(scopes))
        .values_list("character_id", flat=True)
    )


def first_character_with_scopes(
    character_ids: Sequence[int], scopes: Sequence[str]
) -> int | None:
    """The first of ``character_ids`` (in the caller's preference order)
    that holds ``scopes``, or None."""
    ordered = [int(cid) for cid in character_ids if cid]
    holders = character_ids_with_scopes(ordered, scopes)
    return next((cid for cid in ordered if cid in holders), None)
