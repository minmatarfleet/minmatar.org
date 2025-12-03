"""Views for the Discord app, deprecated"""

import logging

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import redirect

from .client import DiscordClient
from users.helpers import make_user_objects

discord = DiscordClient()

logger = logging.getLogger(__name__)
auth_url_discord = f"https://discord.com/api/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_ADMIN_REDIRECT_URL}&response_type=code&scope=identify"  # pylint: disable=line-too-long


def discord_login(request: HttpRequest):  # pylint: disable=unused-argument
    """
    Backend login via Discord

    See `users.router.login()` for frontend (website) login API.

    Redirects the user to Discord; they will be redirected back which will
    be handled by `discord_login_redirect`.

    This backend login is used for...

    1) Admin page access
    2) Authentication during the ESI SSO process for getting/refreshing tokens
    """
    if hasattr(settings, "FAKE_LOGIN_USER_ID"):
        return fake_login(request, settings.FAKE_LOGIN_USER_ID)

    # get next and store in session
    logger.debug("Adding redirect URL to session: %s", request.GET.get("next"))
    request.session["next"] = request.GET.get("next")
    logger.info(
        "Redirecting to Discord for backend login %s", auth_url_discord
    )
    return redirect(auth_url_discord)


def discord_logout(request: HttpRequest):
    logout(request)
    return redirect("/")


def discord_login_redirect(request: HttpRequest):
    logger.debug(
        "[DISCORD VIEW] :: Recived discord callback with code: %s",
        request.GET.get("code"),
    )
    code = request.GET.get("code")
    user = discord.exchange_code(code, settings.DISCORD_ADMIN_REDIRECT_URL)

    if not user:
        redirect_to_error_page(request, "exchange_token_failed")

    django_user = make_user_objects(user)

    login(request, django_user)

    if request.session.get("next"):
        next_url = request.session["next"]
    else:
        next_url = "/admin"

    logger.info(
        "[DISCORD VIEW] :: backend logon successful for %s, next = %s",
        django_user.username,
        next_url,
    )

    return redirect(next_url)


def redirect_to_error_page(request, error_code):
    """Redirects to a frontend authentication error page"""
    try:
        redirect_url = request.session["authentication_redirect_url"]
    except KeyError:
        redirect_url = "https://my.minmatar.org/auth/login"

    redirect_url = redirect_url + "?error=" + error_code
    logger.info("Redirecting to error URL... %s", redirect_url)
    return redirect(redirect_url)


def fake_login(request: HttpRequest, user_id):
    django_user = User.objects.get(id=user_id)
    django_user.is_superuser = True
    django_user.is_staff = True
    django_user.save()

    login(request, django_user)

    logger.info("Fake login as user %s", django_user.username)

    return redirect("/admin")
