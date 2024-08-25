import logging

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from discord.client import DiscordClient
from discord.models import DiscordUser
from discord.tasks import sync_discord_user
from groups.tasks import update_affiliation

from .helpers import get_user_profile
from .schemas import UserProfileSchema

logger = logging.getLogger(__name__)
auth_url_discord = f"https://discord.com/api/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URL}&response_type=code&scope=identify"  # pylint: disable=line-too-long
router = Router(tags=["Authentication"])
discord = DiscordClient()


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/login",
    summary="Login with discord",
    description="This is URL that will redirect to Discord and generate a token, redirecting back to the URL specified in the redirect_url query parameter.",  # pylint: disable=line-too-long
)
def login(request, redirect_url: str):
    logger.info(f"Adding redirect URL to session: {redirect_url}")
    request.session["authentication_redirect_url"] = redirect_url
    logger.info(f"Current session: {request.session}")
    return redirect(auth_url_discord)


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

    payload = {
        "user_id": django_user.id,
        "username": user["username"],
        "avatar": f"https://cdn.discordapp.com/avatars/{django_user.discord_user.id}/{django_user.discord_user.avatar}.png",
        "is_superuser": django_user.is_superuser,
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    return redirect(
        request.session["authentication_redirect_url"]
        + "?token="
        + encoded_jwt_token
    )


@router.get(
    "/{user_id}/profile",
    summary="Get user by ID",
    description="This will return the user's information based on the ID of the user.",
    response={
        200: UserProfileSchema,
        404: ErrorResponse,
    },
)
def get_user_by_id(request, user_id: int):
    if not User.objects.filter(id=user_id).exists():
        return 404, {"detail": "User not found."}
    return get_user_profile(user_id)


@router.get(
    "",
    summary="Search for user profiles",
    description="This will search for users based on the query provided.",
    response={
        200: UserProfileSchema,
        404: ErrorResponse,
    },
)
def get_user_by_username(request, username: str):
    if not User.objects.filter(username=username).exists():
        return 404, {"detail": "User not found."}
    user = User.objects.get(username=username)
    return get_user_profile(user.id)


@router.delete(
    "/delete",
    summary="Delete account and all associated data",
    description="This will delete the user account and all associated data. This action is irreversible.",
    auth=AuthBearer(),
)
def delete_account(request):
    request.user.delete()
    request.session.flush()
    return "Account deleted successfully"


@router.post(
    "/{user_id}/sync",
    summary="Sync user with Discord",
    description="This will sync the user with Discord.",
    auth=AuthBearer(),
)
def sync_user(request, user_id: int):
    update_affiliation(user_id)
    sync_discord_user(user_id)
    return "User synced successfully"
