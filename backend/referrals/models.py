from django.db import models
from django.contrib.auth.models import User


class ReferralClick(models.Model):
    page = models.CharField(max_length=60)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    identifier = models.CharField(max_length=80)

    class Meta:
        unique_together = (("page", "user", "identifier"),)
