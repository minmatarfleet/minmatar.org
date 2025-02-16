from django.contrib.auth.models import User
from django.db import models


class UserSubscription(models.Model):
    """A subscription by a user for push notifications"""

    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=False, blank=False
    )

    subscription = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True, null=True)
