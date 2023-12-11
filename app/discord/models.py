from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class DiscordUser(models.Model):
    id = models.BigIntegerField(primary_key=True)
    discord_tag = models.CharField(max_length=100)
    avatar = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="discord_user")
