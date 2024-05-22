import logging

import requests
from django.contrib.auth.models import Group, User
from django.db import models
from esi.clients import EsiClientProvider

from eveonline.models import EvePrimaryCharacter
from fittings.models import EveDoctrine
from fleets.motd import get_motd
from fleets.notifications import get_fleet_discord_notification

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


# Create your models here.
class EveFleet(models.Model):
    """
    Model for storing a fleet in our database
    """

    fleet_types = (
        ("stratop", "Strategic Operation"),
        ("non_strategic", "Non Strategic Operation"),
        ("training", "Training Operation"),
    )
    description = models.TextField(blank=True)
    type = models.CharField(max_length=32, choices=fleet_types)

    start_time = models.DateTimeField()

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    audience = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True
    )
    doctrine = models.ForeignKey(
        EveDoctrine, on_delete=models.SET_NULL, null=True, blank=True
    )
    location = models.CharField(max_length=255, blank=True)
    location_id = models.BigIntegerField(null=True, blank=True)

    @property
    def token(self):
        eve_character = EvePrimaryCharacter.objects.get(
            character__token__user=self.created_by
        ).character
        return eve_character.token.valid_access_token()

    @property
    def fleet_commander(self):
        return EvePrimaryCharacter.objects.get(
            character__token__user=self.created_by
        ).character

    @property
    def notification_channels(self):
        return EveFleetNotificationChannel.objects.filter(group=self.audience)

    def __str__(self):
        return f"{self.created_by} - {self.type} - {self.start_time}"

    def start(self):
        """
        Start the fleet
        """
        user = self.created_by
        eve_character = EvePrimaryCharacter.objects.get(
            character__token__user=user
        ).character
        response = esi.client.Fleets.get_characters_character_id_fleet(
            character_id=eve_character.character_id,
            token=self.token,
        ).results()

        logger.info(response)

        fleet_instance, _ = EveFleetInstance.objects.create(
            id=response["fleet_id"],
            eve_fleet=self,
        )

        fleet_instance.update_motd()
        fleet_instance.update_free_move()

        for channel in self.notification_channels:
            requests.post(
                channel.webhook_url,
                json=get_fleet_discord_notification(
                    self.id,
                    self.get_type_display(),
                    self.fleet_commander.character_name,
                    self.fleet_commander.character_id,
                    self.description,
                ),
                timeout=5,
            )


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

    def update_motd(self):
        """
        Update the motd for the fleet
        """

        motd = get_motd(
            self.eve_fleet.fleet_commander.character_id,
            self.eve_fleet.fleet_commander.character_name,
            self.eve_fleet.location_id,
            self.eve_fleet.location,
            "https://discord.gg/minmatar",
            "Minmatar Fleet Discord",
            (
                self.eve_fleet.doctrine.doctrine_link
                if self.eve_fleet.doctrine
                else "https://my.minmatar.org/ships/fitting/list/"
            ),
            (
                self.eve_fleet.doctrine.name
                if self.eve_fleet.doctrine
                else "Kitchen Sink"
            ),
        )
        token = self.eve_fleet.token
        response = esi.client.Fleets.put_fleets_fleet_id(
            fleet_id=self.id, new_settings={"motd": motd}, token=token
        ).results()
        self.motd = motd
        self.save()
        return response

    def update_free_move(self):
        """
        Update the free move status for the fleet
        """
        token = self.eve_fleet.token
        response = esi.client.Fleets.put_fleets_fleet_id(
            fleet_id=self.id,
            new_settings={"is_free_move": True},
            token=token,
        ).results()
        self.is_free_move = True
        self.save()
        return response

    def update_is_registered_status(self):
        """
        Fetch the advert status for the fleet
        """
        token = self.eve_fleet.token
        response = esi.client.Fleets.get_fleets_fleet_id(
            fleet_id=self.id, token=token
        ).results()

        self.is_registered = response["is_registered"]
        self.save()
        return response

    def update_fleet_members(self):
        """
        Fetch the fleet members for the fleet
        """
        token = self.eve_fleet.token
        response = esi.client.Fleets.get_fleets_fleet_id_members(
            fleet_id=self.id, token=token
        ).results()

        ids_to_resolve = set()
        for esi_fleet_member in response:
            ids_to_resolve.add(esi_fleet_member["character_id"])
            ids_to_resolve.add(esi_fleet_member["ship_type_id"])
            ids_to_resolve.add(esi_fleet_member["solar_system_id"])
        ids_to_resolve = list(ids_to_resolve)
        resolved_ids = esi.client.Universe.post_universe_names(
            ids=ids_to_resolve
        ).results()
        resolved_ids = {x["id"]: x["name"] for x in resolved_ids}

        for esi_fleet_member in response:
            if EveFleetInstanceMember.objects.filter(
                eve_fleet_instance=self,
                character_id=esi_fleet_member["character_id"],
            ).exists():
                existing_fleet_member = EveFleetInstanceMember.objects.get(
                    eve_fleet_instance=self,
                    character_id=esi_fleet_member["character_id"],
                )
                existing_fleet_member.join_time = esi_fleet_member["join_time"]
                existing_fleet_member.role = esi_fleet_member["role"]
                existing_fleet_member.role_name = esi_fleet_member["role_name"]
                existing_fleet_member.ship_type_id = esi_fleet_member[
                    "ship_type_id"
                ]
                existing_fleet_member.solar_system_id = esi_fleet_member[
                    "solar_system_id"
                ]
                existing_fleet_member.squad_id = esi_fleet_member["squad_id"]
                existing_fleet_member.station_id = esi_fleet_member[
                    "station_id"
                ]
                existing_fleet_member.takes_fleet_warp = esi_fleet_member[
                    "takes_fleet_warp"
                ]
                existing_fleet_member.wing_id = esi_fleet_member["wing_id"]
                existing_fleet_member.character_name = resolved_ids[
                    esi_fleet_member["character_id"]
                ]
                existing_fleet_member.ship_name = resolved_ids[
                    esi_fleet_member["ship_type_id"]
                ]
                existing_fleet_member.solar_system_name = resolved_ids[
                    esi_fleet_member["solar_system_id"]
                ]
                existing_fleet_member.save()
            else:
                EveFleetInstanceMember.objects.create(
                    eve_fleet_instance=self,
                    character_id=esi_fleet_member["character_id"],
                    join_time=esi_fleet_member["join_time"],
                    role=esi_fleet_member["role"],
                    role_name=esi_fleet_member["role_name"],
                    ship_type_id=esi_fleet_member["ship_type_id"],
                    solar_system_id=esi_fleet_member["solar_system_id"],
                    squad_id=esi_fleet_member["squad_id"],
                    station_id=esi_fleet_member["station_id"],
                    takes_fleet_warp=esi_fleet_member["takes_fleet_warp"],
                    wing_id=esi_fleet_member["wing_id"],
                    character_name=resolved_ids[
                        esi_fleet_member["character_id"]
                    ],
                    ship_name=resolved_ids[esi_fleet_member["ship_type_id"]],
                    solar_system_name=resolved_ids[
                        esi_fleet_member["solar_system_id"]
                    ],
                )


class EveFleetInstanceMember(models.Model):
    """
    Model for tracking members of a fleet instance
    """

    eve_fleet_instance = models.ForeignKey(
        EveFleetInstance, on_delete=models.CASCADE
    )
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)

    join_time = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=255)
    role_name = models.CharField(max_length=255)
    ship_type_id = models.BigIntegerField()
    ship_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)
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
    webhook_url = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.group} - {self.discord_channel_name}"


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
