from django.contrib.auth.models import Group, User
from django.db import models

from eveonline.models import EveCharacter
from fittings.models import EveDoctrine


# Create your models here.
class EveFleet(models.Model):
    """
    Model for storing a fleet in our database
    """

    fleet_types = (
        ("stratop", "Strategic Operation"),
        ("non_strategic", "Non Strategic Operation"),
        ("casual", "Casual Operation"),
        ("training", "Training Operation"),
    )
    description = models.TextField(blank=True)
    type = models.CharField(max_length=32, choices=fleet_types)
    audience = models.ManyToManyField(Group, blank=True)
    start_time = models.DateTimeField()

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    doctrine = models.ForeignKey(
        EveDoctrine, on_delete=models.SET_NULL, null=True, blank=True
    )
    location = models.CharField(max_length=255, blank=True)


class EveFleetInstance(models.Model):
    """
    Instance of an EVE Online fleet, tracked by ESI
    """

    id = models.BigIntegerField(primary_key=True)
    eve_fleet = models.ForeignKey(EveFleet, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_free_move = models.BooleanField(default=False)
    is_registered = models.BooleanField(default=False)
    motd = models.TextField(blank=True)

    @property
    def active(self):
        return self.end_time is None


class EveFleetInstanceMember(models.Model):
    """
    Model for tracking members of a fleet instance
    """

    eve_fleet_instance = models.ForeignKey(
        EveFleetInstance, on_delete=models.CASCADE
    )
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)

    join_time = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=255)
    role_name = models.CharField(max_length=255)
    ship_type_id = models.BigIntegerField()
    solar_system_id = models.BigIntegerField()
    squad_id = models.IntegerField()
    station_id = models.BigIntegerField(null=True, blank=True)
    takes_fleet_warp = models.BooleanField(default=False)
    wing_id = models.IntegerField()


class EveFleetNotificationChannel(models.Model):
    """
    Model for storing channels for fleet notifications
    """

    discord_channel_id = models.BigIntegerField()
    discord_channel_name = models.CharField(max_length=255)


class EveFleetNotification(models.Model):
    """
    Model for storing fleet notifications
    """

    fleet_notification_types = (
        ("preping", "Preping"),
        ("ping", "Ping"),
    )

    type = models.CharField(max_length=10, choices=fleet_notification_types)
    fleet = models.ForeignKey(EveFleet, on_delete=models.CASCADE)
    channel = models.ForeignKey(
        EveFleetNotificationChannel, on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("type", "fleet")
