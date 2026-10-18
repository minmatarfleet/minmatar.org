"""Django views for mobile EVE SSO completion via django-esi."""

import logging

from esi.decorators import token_required

from users.eve_sso import (
    CharacterOwnerNotVerified,
    eve_login_error_redirect,
    issue_mobile_jwt,
)
from users.redirects import oauth_redirect, safe_login_redirect_url

logger = logging.getLogger(__name__)

MOBILE_LOGIN_REDIRECT = "mobile://auth/callback"


@token_required(scopes="publicData", new=True)
def eve_mobile_sso_complete(request, token):
    redirect_url = safe_login_redirect_url(
        request.session.get("authentication_redirect_url"),
        MOBILE_LOGIN_REDIRECT,
    )

    try:
        jwt_token = issue_mobile_jwt(request, token)
    except CharacterOwnerNotVerified as refused:
        # Keep no token for an owner the site never verified.
        token.delete()
        return oauth_redirect(
            eve_login_error_redirect(redirect_url, refused.code)
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Mobile EVE SSO login failed")
        return oauth_redirect(
            eve_login_error_redirect(redirect_url, "LOGIN_FAILED")
        )

    request.session.pop("authentication_redirect_url", None)
    return oauth_redirect(f"{redirect_url}?token={jwt_token}")
