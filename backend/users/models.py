from django.contrib.auth.models import User
from django.db import models


class UserDesktopSettings(models.Model):
    """Minmatar Fleet desktop app settings (window positions, toggles).

    Stored on the account so they follow the pilot to any PC and the app
    keeps nothing on disk but its session token. The app owns the keys;
    the API only checks size and shape.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="desktop_settings",
    )
    values = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User desktop settings"
        verbose_name_plural = "User desktop settings"

    def __str__(self):
        return f"{self.user.username} · desktop settings"
