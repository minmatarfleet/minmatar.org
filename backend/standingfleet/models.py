from django.db import models


# Create your models here.
class StandingFleetVoiceRecord(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=255)
    minutes = models.IntegerField()

    class Meta:
        indexes = [
            # Index on 'created_on' for queries filtering by creation date
            models.Index(fields=["created_on"], name="created_on_idx"),
            # Index on 'username' for queries filtering by username
            models.Index(fields=["username"], name="username_idx"),
        ]
