import logging

import jwt
from typing import List, Optional
from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.utils import timezone
from ninja import Router
from pydantic import BaseModel

from app.errors import create_error_id
from authentication import AuthBearer
from discord.client import DiscordClient, DiscordError

# from discord.models import DiscordUser
from discord.tasks import sync_discord_user, sync_discord_nickname

# from eveonline.models import EvePlayer
from groups.tasks import update_affiliation

from .helpers import get_user_profile, get_user_profiles, make_user_objects
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
    if hasattr(settings, "FAKE_LOGIN_USER_ID"):
        return fake_login(request, redirect_url)

    logger.debug(f"Adding redirect URL to session: {redirect_url}")
    if not redirect_url:
        redirect_url = "https://my.minmatar.org/auth/login"
    request.session["authentication_redirect_url"] = redirect_url
    logger.debug(f"Current session: {request.session}")
    return redirect(auth_url_discord)


@router.get("/callback", include_in_schema=False)
def callback(
    request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    redirect_url = redirect_url_from_session(request)

    # Note that while `code` is marked optional, the endpoint will not work without it
    if code is None:
        error_id = create_error_id()
        logger.error(
            "No code returned in Discord redirect: %s, %s (%s)",
            error,
            error_description,
            error_id,
        )
        return redirect(f"{redirect_url}?error=DENIED&id={error_id}")

    logger.debug("Recived discord callback with code: ...%s", code[-5:])

    try:
        user = discord.exchange_code(code)
    except DiscordError as e:
        logger.error(
            "Error exchanging Discord code (%s): %d %s",
            e.id,
            e.status_code,
            e.description,
        )
        return redirect(f"{redirect_url}?error={e.code}&id={e.id}")

    logger.debug("Successfully exchanged code for user: %s", user["username"])

    django_user = make_user_objects(user)

    payload = {
        "user_id": django_user.id,
        "username": user["username"],
        "avatar": f"https://cdn.discordapp.com/avatars/{django_user.discord_user.id}/{django_user.discord_user.avatar}.png",
        "is_superuser": django_user.is_superuser,
        "sub": user["username"],
        "iss": request.get_host(),
        "iat": timezone.now(),
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    logger.debug("Signed JWT Token: ...%s", encoded_jwt_token[-5:])

    logger.info("Login success: %s -> %s", django_user.username, redirect_url)
    redirect_url = redirect_url + "?token=" + encoded_jwt_token
    return redirect(redirect_url)


def redirect_url_from_session(request):
    redirect_url = "https://my.minmatar.org/auth/login"
    try:
        redirect_url = request.session["authentication_redirect_url"]
    except KeyError:
        logger.warning("No redirect URL found in session")
    return redirect_url


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
def query_users(request, username: str):
    if not User.objects.filter(username=username).exists():
        return 404, {"detail": "User not found."}
    user = User.objects.get(username=username)
    return get_user_profile(user.id)


@router.get(
    "/profiles",
    summary="Search for user profiles",
    description="This will search for users based on the query provided.",
    response={
        200: List[UserProfileSchema],
        404: ErrorResponse,
    },
)
def query_multiple_users(
    request, username: str = "", ids: str = ""
) -> List[UserProfileSchema]:
    if username:
        # Backwards compatibility with original `query_users()`
        if not User.objects.filter(username=username).exists():
            return 404, {"detail": "User not found."}
        user = User.objects.get(username=username)
        return [get_user_profile(user.id)]

    if ids:
        user_ids = []
        ids = ids.split(",")
        for user_id in ids:
            user_ids.append(int(user_id))
        return get_user_profiles(user_ids)

    return []


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
    sync_discord_nickname(user_id, True)
    return "User synced successfully"


def fake_login(request, redirect_url):
    """Fake user login for local dev server only."""

    user_id = int(settings.FAKE_LOGIN_USER_ID)
    logger.warning("*** FAKE USER LOGIN (id=%d) ***", user_id)

    django_user = User.objects.get(id=user_id)
    payload = {
        "user_id": django_user.id,
        "username": django_user.username,
        "is_superuser": django_user.is_superuser,
        "sub": django_user.username,
        "iss": request.get_host(),
        "iat": timezone.now(),
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    logger.debug("Signed JWT Token: %s", encoded_jwt_token)

    logger.info("Redirecting to authentication URL... %s", redirect_url)
    redirect_url = redirect_url + "?token=" + encoded_jwt_token
    return redirect(redirect_url)
