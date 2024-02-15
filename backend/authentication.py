import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.shortcuts import redirect
from ninja import Router
from ninja.security import HttpBearer

from discord.client import DiscordClient
from discord.models import DiscordUser

auth_url_discord = f"https://discord.com/api/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URL}&response_type=code&scope=identify"  # pylint: disable=line-too-long
router = Router(tags=["Authentication"])
discord = DiscordClient()


class AuthBearer(HttpBearer):
    """Authentication class for Ninja API methods"""

    def authenticate(self, request, token):
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            user = User.objects.get(id=payload["user_id"])
            request.user = user
            return user
        except Exception as e:
            print(e)
            return None


@router.get(
    "/login",
    deprecated=True,
    summary="Login with discord",
    description="This is URL that will redirect to Discord and generate a token, redirecting back to the URL specified in the redirect_url query parameter.",  # pylint: disable=line-too-long
)
def login(request, redirect_url: str):
    request.session["authentication_redirect_url"] = redirect_url
    return redirect(auth_url_discord)


@router.delete(
    "/delete",
    deprecated=True,
    summary="Delete account and all associated data",
    description="This will delete the user account and all associated data. This action is irreversible.",
    auth=AuthBearer(),
)
def delete_account(request):
    request.user.delete()
    request.session.flush()
    return "Account deleted successfully"


@router.get("/callback", include_in_schema=False)
def callback(request, code: str):
    user = discord.exchange_code(code)
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
    else:
        django_user = User.objects.create(username=user["username"])
        django_user.username = user["username"]
        django_user.save()

        discord_user = DiscordUser.objects.create(
            user=django_user,
            id=user["id"],
            discord_tag=user["username"] + "#" + user["discriminator"],
            avatar=user["avatar"],
        )

    permissions = (
        django_user.user_permissions.all()
        | Permission.objects.filter(group__user=django_user)
    )

    permissions = [
        f"{p._meta.app_label}.{p.codename}"  # pylint: disable=protected-access
        for p in permissions
    ]

    payload = {
        "user_id": django_user.id,
        "username": user["username"],
        "avatar": f"https://cdn.discordapp.com/avatars/{django_user.discord_user.id}/{django_user.discord_user.avatar}.png",
        "is_staff": django_user.is_staff,
        "is_superuser": django_user.is_superuser,
        "permissions": permissions,
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    return redirect(
        request.session["authentication_redirect_url"]
        + "?token="
        + encoded_jwt_token
    )


class UnauthorizedError(Exception):
    pass
