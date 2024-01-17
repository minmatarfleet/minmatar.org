import jwt
from ninja import Router
from ninja.security import HttpBearer
from discord.models import DiscordUser
from discord.client import DiscordClient
from django.contrib.auth.models import User
from django.conf import settings

router = Router()
discord = DiscordClient()


@router.get("/token")
def get_token(request, token: str):
    user = discord.exchange_code(token)
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
    }
    encoded_jwt_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    return {"token": encoded_jwt_token}


class AuthBearer(HttpBearer):
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
