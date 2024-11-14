from django.db import models


# Create your models here.
class StandingFleetVoiceRecord(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=255)
    minutes = models.IntegerField()
