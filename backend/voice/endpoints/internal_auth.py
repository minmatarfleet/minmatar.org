"""Auth and helpers for /api/voice/internal/*, the voice service's paths.

Served only on the edge's ``internal`` entrypoint (no host port; the public
``api`` router excludes the path), left out of the public schema, and
checked against ``VOICE_INTERNAL_SECRET``. With no secret configured every
request is refused (401).
"""

import hmac

from django.conf import settings
from ninja.security import APIKeyHeader

from voice.publisher import publish_character

SECRET_HEADER = "X-Voice-Secret"


class InternalSecret(APIKeyHeader):
    param_name = SECRET_HEADER

    def authenticate(self, request, key):
        secret = settings.VOICE_INTERNAL_SECRET
        if not secret or not key:
            return None
        if hmac.compare_digest(str(key), str(secret)):
            return "voice-service"
        return None


def record_for(identity):
    if identity is None:
        return 404, {"detail": "unknown"}
    return 200, publish_character(identity.character_id)
