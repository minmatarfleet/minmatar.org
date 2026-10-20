import logging
from typing import List, Sequence

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel

from audit.models import AuditEntry
from discord.models import DiscordUser
from esi.models import Token
from eveonline.models import EvePlayer, EveCharacter
from eveonline.helpers.characters.identity import primary_character_for_user
from eveonline.scopes import (
    NEW_CHARACTER_SCOPE_GROUPS,
    TokenType,
    scope_names,
    scopes_for_groups,
    token_satisfies_type,
    token_type_str,
)
from tribes.models import (
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

logger = logging.getLogger(__name__)


class CharacterResponse(BaseModel):
    character_id: int
    character_name: str
    type: str = "Public"
    scopes: List[str]
    is_primary: bool = False


def user_primary_character(user: User) -> EveCharacter | None:
    """Returns the primary character for a particular User.

    One query per call; for many users use
    :func:`eveonline.helpers.characters.identity.primary_characters_for_users`.
    """
    return primary_character_for_user(user)


def user_characters(user: User) -> List[EveCharacter]:
    """Returns all the EveCharacters for a particular User.

    Only characters whose ``EveCharacter.user`` is this user: legacy
    characters linked through their token alone are not listed here (they
    still count as the user's in the batch helpers in ``identity``).
    """
    return EveCharacter.objects.filter(user=user).all()


def related_characters(character: EveCharacter) -> List[EveCharacter]:
    """Returns all EveCharacters belonging to the same user as the given character."""
    if not character or not character.user_id:
        return []
    return list(
        EveCharacter.objects.filter(user_id=character.user_id).order_by(
            "character_name"
        )
    )


def character_primary(character: EveCharacter) -> EveCharacter | None:
    """Returns the primary character for a character"""
    if not character:
        return None
    if character.user_id:
        return user_primary_character(character.user)
    token = character.token
    if token is not None and token.user_id:
        return user_primary_character(token.user)
    return None


def _nickname_taken(nickname: str, exclude_player: EvePlayer | None) -> bool:
    """True when another player already holds this nickname (case-insensitive)."""
    if not nickname:
        return False
    queryset = EvePlayer.objects.filter(nickname__iexact=nickname)
    if exclude_player is not None and exclude_player.pk:
        queryset = queryset.exclude(pk=exclude_player.pk)
    return queryset.exists()


def _fallback_player_nickname(player: EvePlayer, *, avoid: str) -> str:
    """A unique nickname that is not the character name being claimed."""
    base = ""
    if player.user_id and player.user.username:
        base = player.user.username
    if not base:
        base = f"player{player.pk or 'x'}"
    avoid_fold = (avoid or "").casefold()
    pk = player.pk or "x"
    candidates = [base, f"{base}__u{pk}", f"{base}__u{pk}__2"]
    for candidate in candidates:
        if not candidate or candidate.casefold() == avoid_fold:
            continue
        if not _nickname_taken(candidate, player):
            return candidate[:255]
    return f"{base}__u{pk}__3"[:255]


def _available_player_nickname(
    desired: str, *, exclude_player: EvePlayer | None, user: User
) -> str:
    """Prefer the character name; otherwise a unique fallback that will save."""
    cleaned = (desired or "").strip()
    if cleaned and not _nickname_taken(cleaned, exclude_player):
        return cleaned[:255]
    if exclude_player is not None:
        return _fallback_player_nickname(exclude_player, avoid=cleaned)
    base = user.username or f"user{user.pk}"
    for candidate in (base, f"{base}__u{user.pk}"):
        if cleaned and candidate.casefold() == cleaned.casefold():
            continue
        if not _nickname_taken(candidate, None):
            return candidate[:255]
    return f"{base}__u{user.pk}__2"[:255]


class PrimaryCharacterHeld(Exception):
    """Another account still has this character as its main.

    Setting the main must not move it. The message names both Discord
    accounts and tells the pilot to delete the one that already has it.
    """

    def __init__(self, holder: User, claimer: User):
        self.holder = holder
        self.claimer = claimer
        super().__init__(main_held_message(holder, claimer))


def discord_login_name(user: User) -> str | None:
    """Discord username for a website account, without a #0 discriminator."""
    tag = (
        DiscordUser.objects.filter(user=user)
        .values_list("discord_tag", flat=True)
        .first()
    )
    if not tag:
        return None
    name, _, discriminator = tag.partition("#")
    if discriminator in ("", "0"):
        return name or tag
    return tag


def main_held_message(holder: User, claimer: User) -> str:
    """Name both Discord logins and point at deleting the account that has the main."""
    held = discord_login_name(holder)
    current = discord_login_name(claimer) or claimer.username
    if held:
        return (
            f"This character is already the main on the Discord account {held}. "
            f"You are trying to move it to {current}. "
            f"Log in as {held} on the Minmatar Fleet website, open Account, "
            "and delete that account. Then sign in as "
            f"{current} and set your main again."
        )
    return (
        "This character is already the main on a website account with no "
        f"Discord login (username {holder.username}). "
        f"You are trying to move it to {current}. "
        "Log in as that website account on the Minmatar Fleet website, "
        "open Account, and delete it. Then sign in as "
        f"{current} and set your main again."
    )


def other_main_holder(character: EveCharacter, user: User) -> User | None:
    """The other website user who still has this character as their main."""
    player = (
        EvePlayer.objects.filter(primary_character=character)
        .exclude(user=user)
        .select_related("user")
        .first()
    )
    if player is None or player.user_id is None:
        return None
    return player.user


def set_primary_character(user: User, character: EveCharacter):
    """Sets the primary character for a user"""
    holder = other_main_holder(character, user)
    if holder is not None:
        raise PrimaryCharacterHeld(holder, user)
    with transaction.atomic():
        current_primary = user_primary_character(user)
        if current_primary and (current_primary != character):
            AuditEntry.objects.create(
                user=user,
                character=character,
                old_character_id=current_primary.character_id,
                category="primary_char",
                summary=(
                    f"User {user.username} set primary character to "
                    f"{character.character_name}"
                ),
            )
            old_player = user_player(user)
            if old_player and old_player.primary_character == current_primary:
                old_player.primary_character = None
                old_player.save()

        character.user = user
        character.save()

        desired = character.character_name or ""
        player = user_player(user)
        if player:
            player.primary_character = character
            if desired.strip():
                player.nickname = _available_player_nickname(
                    desired, exclude_player=player, user=user
                )
            player.save()
        else:
            EvePlayer.objects.create(
                user=user,
                primary_character=character,
                nickname=_available_player_nickname(
                    desired or user.username,
                    exclude_player=None,
                    user=user,
                ),
            )


def user_player(user: User) -> EvePlayer | None:
    return EvePlayer.objects.filter(user=user).first()


def orphan_character(
    character: EveCharacter, *, acting_user: User | None = None
) -> None:
    """Detach a character from its user and ESI tokens; keep synced EVE data."""
    for mc in TribeGroupMembershipCharacter.objects.filter(
        character=character
    ).select_related("membership"):
        TribeGroupMembershipCharacterHistory.objects.create(
            membership=mc.membership,
            character=character,
            action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            at=timezone.now(),
            by=acting_user,
            leave_reason=TribeGroupMembershipCharacterHistory.LEAVE_REASON_VOLUNTARY,
        )
        mc.delete()

    character.user = None
    character.token = None
    character.save(update_fields=["user", "token"])
    Token.objects.filter(character_id=character.character_id).delete()


def _normalize_token_level(level: str) -> str:
    """Map legacy token level names to current TokenType values."""
    legacy = {
        "CEO": "Director",
        "Freight": "Market",
        "Advanced": "Industry",
        "Campaign": "FactionWarfare",
    }
    return legacy.get(level, level)


def merge_scope_groups(
    existing: List[str] | None, *groups: str | None
) -> List[str]:
    """Return scope groups with duplicates removed, preserving order."""
    result = list(existing or [])
    for group in groups:
        normalized = _normalize_token_level((group or "").strip())
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def character_configured_scope_groups(character: EveCharacter) -> List[str]:
    """Scope groups explicitly configured for a character."""
    groups = merge_scope_groups(getattr(character, "esi_scope_groups", None))
    if not groups and character.esi_token_level:
        return merge_scope_groups([], character.esi_token_level)
    if character.esi_token_level:
        groups = merge_scope_groups(
            groups, _normalize_token_level(character.esi_token_level)
        )
    return groups


def character_desired_scopes(character: EveCharacter) -> List[str]:
    """Union of scopes for all of the character's scope groups."""
    groups = character_configured_scope_groups(character)
    if not groups:
        return []
    return scopes_for_groups(groups)


def scope_groups_for_token_add(
    character: EveCharacter | None,
    token_type: TokenType,
    extra_groups: Sequence[TokenType] = (),
) -> List[str]:
    """Scope groups to request in SSO when adding token_type to a character.

    extra_groups are the ones picked in the add-character dialog. A character
    added without naming one also gets the new-character groups. Public is
    the guest login and never widens.
    """
    if token_type == TokenType.PUBLIC:
        return merge_scope_groups([], token_type_str(token_type))
    existing: List[str] = []
    if character is not None:
        existing = character_configured_scope_groups(character)
    groups = merge_scope_groups(
        existing,
        token_type_str(token_type),
        *(group.value for group in extra_groups),
    )
    if character is None:
        groups = merge_scope_groups(
            groups, *(group.value for group in NEW_CHARACTER_SCOPE_GROUPS)
        )
    return groups


def scope_groups_granted(
    token: Token,
    token_type: TokenType,
    extra_groups: Sequence[TokenType] = (),
) -> List[str]:
    """The group that was asked for, plus every other one the token holds.

    The callback reads the extra and new-character groups off the token
    rather than assuming the SSO request carried them.
    """
    groups = merge_scope_groups([], token_type_str(token_type))
    if token_type == TokenType.PUBLIC:
        return groups
    for group in [*extra_groups, *NEW_CHARACTER_SCOPE_GROUPS]:
        if token_satisfies_type(token, group):
            groups = merge_scope_groups(groups, group.value)
    return groups


def scopes_for_token_add(
    character: EveCharacter | None,
    token_type: TokenType,
    extra_groups: Sequence[TokenType] = (),
) -> List[str]:
    """Scopes to request so a re-auth cannot come back narrower than today.

    The callback keeps a new token only when it has at least as many scopes as
    the one it would replace. Asking for the configured groups alone drops
    scopes the pilot already granted, the new token is discarded, and the
    page they returned to looks unchanged.
    """
    scopes = set(
        scopes_for_groups(
            scope_groups_for_token_add(character, token_type, extra_groups)
        )
    )
    token = (
        getattr(character, "token", None) if character is not None else None
    )
    if token is not None:
        scopes.update(scope_names(token))
    return sorted(scopes)


def character_has_market_scopes(character: EveCharacter) -> bool:
    """True if the character is configured with Market or Executor scopes."""
    groups = character_configured_scope_groups(character)
    return (
        TokenType.MARKET.value in groups or TokenType.EXECUTOR.value in groups
    )


def user_ids_with_market_scopes() -> set[int]:
    """User IDs that own at least one non-suspended Market/Executor character."""
    user_ids = set()
    for character in (
        EveCharacter.objects.filter(user_id__isnull=False)
        .exclude(esi_suspended=True)
        .only("user_id", "esi_scope_groups", "esi_token_level")
    ):
        if character_has_market_scopes(character):
            user_ids.add(character.user_id)
    return user_ids


def market_scope_character_ids(
    *, user_ids: set[int] | None = None
) -> list[int]:
    """
    Character IDs with Market/Executor scopes.
    When user_ids is set, only characters owned by those users are considered.
    """
    qs = EveCharacter.objects.filter(user__isnull=False).exclude(
        esi_suspended=True
    )
    if user_ids is not None:
        qs = qs.filter(user_id__in=user_ids)
    ids = []
    for character in qs.only(
        "character_id", "esi_scope_groups", "esi_token_level"
    ):
        if character_has_market_scopes(character):
            ids.append(character.character_id)
    return ids
