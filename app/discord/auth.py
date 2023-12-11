from django.contrib.auth.backends import BaseBackend
from .models import DiscordUser
from django.contrib.auth.models import User


class DiscordAuthenticationBackend(BaseBackend):
    def authenticate(self, request, user) -> DiscordUser:
        find_user = DiscordUser.objects.filter(id=user["id"])
        if len(find_user) == 0:
            print("User was not found. Saving...")
            new_user = DiscordUser.objects.create_new_discord_user(user)
            print(new_user)
            return new_user
        print("User was found. Returning...")
        return find_user

    def get_user(self, user_id):
        try:
            return DiscordUser.objects.get(pk=user_id)
        except DiscordUser.DoesNotExist:
            return None
