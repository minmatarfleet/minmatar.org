"""Views for the Discord app, deprecated"""

import logging

import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import redirect

from .models import DiscordUser

# Create your views here.
logger = logging.getLogger(__name__)
auth_url_discord = f"https://discord.com/api/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_ADMIN_REDIRECT_URL}&response_type=code&scope=identify"  # pylint: disable=line-too-long


def discord_login(request: HttpRequest):  # pylint: disable=unused-argument
    if hasattr(settings, "FAKE_LOGIN_USER_ID"):
        return fake_login(request)

    # get next and store in session
    logger.info("Adding redirect URL to session: %s", request.GET.get("next"))
    request.session["next"] = request.GET.get("next")
    logger.info("Redirecting to Discord for login %s", auth_url_discord)
    return redirect(auth_url_discord)


def discord_logout(request: HttpRequest):
    logout(request)
    return redirect("/")


def discord_login_redirect(request: HttpRequest):
    logger.info(
        "[DISCORD VIEW] :: Recived discord callback with code: %s",
        request.GET.get("code"),
    )
    code = request.GET.get("code")
    user = exchange_code(code)

    if not user:
        redirect_to_error_page(request, "exchange_token_failed")

    if DiscordUser.objects.filter(id=user["id"]).exists():
        logger.info("[DISCORD VIEW] :: User already exists. Logging in...")
        discord_user = DiscordUser.objects.get(id=user["id"])
        discord_user.discord_tag = (
            user["username"] + "#" + user["discriminator"]
        )
        discord_user.avatar = user["avatar"]
        discord_user.save()

        django_user = User.objects.get(username=discord_user.user.username)
        django_user.username = user["username"]
        django_user.save()

        login(request, django_user)

        if request.session.get("next"):
            logger.info(
                "[DISCORD VIEW] :: Redirecting to next URL: %s",
                request.session["next"],
            )
            return redirect(request.session["next"])
        logger.info("[DISCORD VIEW] :: Redirecting to admin panel")
        return redirect("/admin")

    logger.info("[DISCORD VIEW] :: User does not exist. Creating user...")
    django_user = User.objects.create(username=user["username"])
    django_user.username = user["username"]
    django_user.save()

    discord_user = DiscordUser.objects.create(
        user=django_user,
        id=user["id"],
        discord_tag=user["username"] + "#" + user["discriminator"],
        avatar=user["avatar"],
    )

    login(request, django_user)
    if request.session.get("next"):
        logger.info(
            "[DISCORD VIEW] :: Redirecting to next URL: %s",
            request.session["next"],
        )
        return redirect(request.session["next"])
    logger.info("[DISCORD VIEW] :: Redirecting to admin panel")
    return redirect("/admin")


def exchange_code(code: str):
    """Exchange a Discord OAuth2 code for an access token"""
    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.DISCORD_ADMIN_REDIRECT_URL,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers=headers,
        timeout=10,
    )
    logger.info("[DISCORD VIEW] :: Discord OAuth2 Token Body: %s", data)
    logger.info(
        "[DISCORD VIEW] :: Discord OAuth2 Token Response: %s", response.json()
    )
    if response.status_code >= 400:
        logger.error("Error %d exchanging Discord code", response.status_code)
        return None
    # response.raise_for_status()
    credentials = response.json()
    access_token = credentials["access_token"]
    response = requests.get(
        "https://discord.com/api/v6/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    user = response.json()
    return user


def redirect_to_error_page(request, error_code):
    """Redirects to a frontend authentication error page"""
    try:
        redirect_url = request.session["authentication_redirect_url"]
    except KeyError:
        redirect_url = "https://my.minmatar.org/auth/login"

    redirect_url = redirect_url + "?error=" + error_code
    logger.info("Redirecting to error URL... %s", redirect_url)
    return redirect(redirect_url)


def fake_login(request: HttpRequest):
    django_user = User.objects.get(id=settings.FAKE_LOGIN_USER_ID)
    django_user.is_superuser = True
    django_user.is_staff = True
    django_user.save()

    login(request, django_user)

    logger.info("Fake login as user %s", django_user.username)

    return redirect("/admin")
