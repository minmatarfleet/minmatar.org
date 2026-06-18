"""Django views for mobile EVE SSO completion via django-esi."""

from esi.decorators import token_required

from users.eve_sso import eve_login_error_redirect, issue_mobile_jwt
from users.redirects import oauth_redirect


@token_required(scopes="publicData", new=True)
def eve_mobile_sso_complete(request, token):
    redirect_url = request.session.get(
        "authentication_redirect_url", "mobile://auth/callback"
    )

    try:
        jwt_token = issue_mobile_jwt(request, token)
    except Exception:
        return oauth_redirect(
            eve_login_error_redirect(redirect_url, "LOGIN_FAILED")
        )

    request.session.pop("authentication_redirect_url", None)
    return oauth_redirect(f"{redirect_url}?token={jwt_token}")
