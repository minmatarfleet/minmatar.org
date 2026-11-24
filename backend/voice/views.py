"""EVE SSO completion for /voice (public info only, no site account)."""

import logging
from urllib.parse import urlencode

from esi.decorators import token_required

from app.links import site_url
from eveonline.client import EsiClient
from users.redirects import oauth_redirect, safe_login_redirect_url
from voice.identity import issue_voice_jwt, upsert_identity
from voice.models import VoiceAuditEvent

logger = logging.getLogger(__name__)

SESSION_KEY = "voice_redirect_url"
STATE_SESSION_KEY = "voice_login_state"


def default_voice_login_url() -> str:
    return site_url("/voice/login")


def _public_affiliation(character_id: int) -> tuple[int | None, int | None]:
    """Corporation and alliance from ESI's public affiliation lookup."""
    try:
        response = EsiClient(None).get_character_affiliations([character_id])
        rows = response.data if response.success() else []
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Voice sign-in: affiliation lookup failed")
        return None, None
    for row in rows or []:
        if int(row.get("character_id", 0)) == int(character_id):
            return row.get("corporation_id"), row.get("alliance_id")
    return None, None


@token_required(scopes="publicData", new=True)
def voice_sso_complete(request, token):
    redirect_url = safe_login_redirect_url(
        request.session.pop(SESSION_KEY, None), default_voice_login_url()
    )
    state = request.session.pop(STATE_SESSION_KEY, "") or ""
    try:
        corporation_id, alliance_id = _public_affiliation(token.character_id)
        identity = upsert_identity(
            token.character_id,
            token.character_name,
            owner_hash=token.character_owner_hash or "",
            corporation_id=corporation_id,
            alliance_id=alliance_id,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Voice sign-in failed")
        return oauth_redirect(f"{redirect_url}?error=LOGIN_FAILED")
    finally:
        # Public info only: keep no ESI token for a voice sign-in, unless
        # the character's site account already holds this one.
        if token.user_id is None:
            token.delete()
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_SIGN_IN, character_id=identity.character_id
    )
    # The website keeps the token only when state matches the cookie it set
    # when this browser started the sign-in.
    query = urlencode({"token": issue_voice_jwt(identity), "state": state})
    return oauth_redirect(f"{redirect_url}?{query}")
