"""Views for the Discord app, deprecated"""
import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpRequest
from django.shortcuts import redirect
from django.contrib.auth.models import User
from .models import DiscordUser

# Create your views here.

auth_url_discord = f"https://discord.com/api/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URL}&response_type=code&scope=identify"  # pylint: disable=line-too-long


def discord_login(request: HttpRequest):  # pylint: disable=unused-argument
    return redirect(auth_url_discord)


def discord_logout(request: HttpRequest):
    logout(request)
    return redirect("/")


def discord_login_redirect(request: HttpRequest):
    code = request.GET.get("code")
    user = exchange_code(code)

    if DiscordUser.objects.filter(id=user["id"]).exists():
        print("User was found. Logging in...")
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

        return redirect("/")

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
    return redirect("/")


def exchange_code(code: str):
    """Exchange a Discord OAuth2 code for an access token"""
    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.DISCORD_REDIRECT_URL,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers=headers,
        timeout=10,
    )
    credentials = response.json()
    access_token = credentials["access_token"]
    response = requests.get(
        "https://discord.com/api/v6/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    user = response.json()
    return user
