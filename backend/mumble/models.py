import secrets
import string

from django.contrib.auth.models import User
from django.db import models

MUMBLE_ACCESS_PASSWORD_LENGTH = 20


def generate_password():
    possible_chars = string.ascii_letters + string.digits + string.punctuation
    return "".join(
        (secrets.choice(possible_chars))
        for i in range(MUMBLE_ACCESS_PASSWORD_LENGTH)
    )


class MumbleAccessManager(models.Manager):
    """
    Custom manager for MumbleAccess model
    """

    def create_mumble_access(self, user):
        mumble_access = self.create(user=user, password=generate_password())
        return mumble_access


class MumbleAccess(models.Model):
    """Represents Mumble access information"""

    objects = MumbleAccessManager()
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="mumble_user"
    )
    password = models.CharField(max_length=MUMBLE_ACCESS_PASSWORD_LENGTH)

    def save(self, *args, **kwargs):
        if not self.password:
            self.password = generate_password()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.user.username)
