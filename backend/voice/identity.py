"""Signing in to /voice, and the bearer auth voice endpoints use.

Guests sign in with EVE (``publicData`` only) and get a voice JWT: it names
a ``VoiceIdentity``, never a Django user, and carries ``aud: voice`` so it
can't be used anywhere else (``AuthBearer`` rejects tokens with an
audience). Members already signed in to the site use their own token and
pick one of their characters.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import jwt
from django.contrib.auth.models import AnonymousUser, User
from django.utils import timezone
from ninja.security import HttpBearer

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter
from users.jwt_auth import decode_audience_jwt, decode_user_jwt, encode_jwt
from voice.models import VoiceAuditEvent, VoiceGrant, VoiceIdentity

logger = logging.getLogger(__name__)

VOICE_AUDIENCE = "voice"
VOICE_SESSION_DAYS = 30


def issue_voice_jwt(identity: VoiceIdentity) -> str:
    now = timezone.now()
    return encode_jwt(
        {
            "aud": VOICE_AUDIENCE,
            "voice_identity_id": identity.id,
            "character_id": identity.character_id,
            "character_name": identity.character_name,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=VOICE_SESSION_DAYS)).timestamp()),
        }
    )


def decode_voice_jwt(token: str) -> dict:
    return decode_audience_jwt(token, VOICE_AUDIENCE)


def upsert_identity(
    character_id: int,
    character_name: str,
    owner_hash: str = "",
    corporation_id: int | None = None,
    alliance_id: int | None = None,
) -> VoiceIdentity:
    """Create or refresh the identity. A new owner hash means the character
    changed hands: its certificates and stored grants are revoked."""
    identity, created = VoiceIdentity.objects.get_or_create(
        character_id=int(character_id),
        defaults={
            "character_name": character_name,
            "owner_hash": owner_hash,
            "corporation_id": corporation_id,
            "alliance_id": alliance_id,
        },
    )
    if created:
        return identity
    if (
        owner_hash
        and identity.owner_hash
        and owner_hash != identity.owner_hash
    ):
        revoke_identity_access(identity)
        VoiceAuditEvent.record(
            VoiceAuditEvent.KIND_OWNER_CHANGED,
            character_id=identity.character_id,
        )
    identity.character_name = character_name or identity.character_name
    if owner_hash:
        identity.owner_hash = owner_hash
    if corporation_id:
        identity.corporation_id = corporation_id
        identity.alliance_id = alliance_id
    identity.save()
    return identity


def revoke_identity_access(identity: VoiceIdentity) -> None:
    # pylint: disable=import-outside-toplevel
    from voice.publisher import unpublish_certificate

    for cert_hash in identity.certificates.values_list("cert_hash", flat=True):
        unpublish_certificate(cert_hash)
    identity.certificates.all().delete()
    identity.tokens.all().delete()
    VoiceGrant.objects.filter(
        character_id=identity.character_id, expires_at__isnull=True
    ).update(expires_at=timezone.now())


def member_identity(
    user: User, character_id: int | None
) -> VoiceIdentity | None:
    """The identity for one of a signed-in member's characters.

    ``character_id`` must be theirs; without it, their primary character.
    """
    characters = EveCharacter.objects.filter(user=user).select_related("token")
    if character_id:
        character = characters.filter(character_id=character_id).first()
    else:
        character = user_primary_character(user)
    if character is None:
        return None
    owner_hash = ""
    if character.token is not None:
        owner_hash = character.token.character_owner_hash or ""
    return upsert_identity(
        character.character_id,
        character.character_name,
        owner_hash=owner_hash,
        corporation_id=character.corporation_id,
        alliance_id=character.alliance_id,
    )


class VoiceAuth(HttpBearer):
    """A voice JWT (guest) or a site JWT (member).

    Sets ``request.voice_identity`` for guests and ``request.user`` for
    members; endpoints call ``request_identity`` to get the character.
    """

    def authenticate(self, request, token):
        try:
            payload = decode_voice_jwt(token)
        except jwt.InvalidTokenError:
            payload = None
        if payload is not None:
            identity = VoiceIdentity.objects.filter(
                id=payload.get("voice_identity_id"),
                character_id=payload.get("character_id"),
            ).first()
            if identity is None:
                return None
            request.voice_identity = identity
            request.user = AnonymousUser()
            return identity
        try:
            payload = decode_user_jwt(token)
        except jwt.InvalidTokenError:
            return None
        user = User.objects.filter(id=payload.get("user_id")).first()
        if user is None or not user.is_active:
            return None
        request.user = user
        request.voice_identity = None
        return user


def request_identity(request, character_id: int | None = None):
    """The character this voice request acts as, or None."""
    identity = getattr(request, "voice_identity", None)
    if identity is not None:
        return identity
    if request.user.is_authenticated:
        return member_identity(request.user, character_id)
    return None
