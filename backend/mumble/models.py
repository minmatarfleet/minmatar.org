from django.contrib.auth.models import User
from django.db import models
import secrets
import string

MUMBLE_ACCESS_PASSWORD_LENGTH = 20

class MumbleAccessManager(models.Manager):
    def _generate_password(self):
        possible_chars = string.ascii_letters + string.digits + string.punctuation
        return "".join((secrets.choice(possible_chars)) for i in range(MUMBLE_ACCESS_PASSWORD_LENGTH))

    def create_mumble_access(self, user):
        mumble_access = self.create(user=user, password=self._generate_password())
        return mumble_access

class MumbleAccess(models.Model):
    """Represents Mumble access information"""

    objects = MumbleAccessManager()
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="mumble_user" 
    )
    password = models.CharField(max_length=MUMBLE_ACCESS_PASSWORD_LENGTH)

    def __str__(self) -> str:
        return self.id