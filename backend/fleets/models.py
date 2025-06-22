import logging

import requests
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils import timezone
from esi.clients import EsiClientProvider

from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveLocation
from eveonline.helpers.characters import user_primary_character
from fittings.models import EveDoctrine
from fleets.motd import get_motd
from fleets.notifications import get_fleet_discord_notification

discord = DiscordClient()
esi = EsiClientProvider()
logger = logging.getLogger(__name__)


# Create your models here.
class EveFleet(models.Model):
    """
    Model for storing a fleet in our database
    """

    fleet_types = (
        ("strategic", "Strategic Operation"),
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
        "EveFleetAudience", on_delete=models.SET_NULL, null=True, blank=True
    )
    doctrine = models.ForeignKey(
        EveDoctrine, on_delete=models.SET_NULL, null=True, blank=True
    )
    location = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    disable_motd = models.BooleanField(null=True, default=False)

    fleet_statuses = (
        ("pending", "Pending"),
        ("active", "Active"),
        ("complete", "Complete"),
        ("cancelled", "Cancelled"),
        ("unknown", "Unknown"),
    )
    status = models.CharField(
        max_length=32, choices=fleet_statuses, default="unknown"
    )

    @property
    def token(self):
        if self.fleet_commander and self.fleet_commander.token:
            return self.fleet_commander.token.valid_access_token()
        else:
            return None

    @property
    def fleet_commander(self):
        return user_primary_character(self.created_by)

    def __str__(self):
        return f"{self.created_by} - {self.type} - {self.start_time}"

    def start(self, character_id: int | None = None):
        """
        Start the fleet
        """
        logger.info("Starting fleet %s", self.id)

        user = self.created_by
        if character_id:
            eve_character = EveCharacter.objects.get(character_id=character_id)
        else:
            eve_character = user_primary_character(user)

        esi_response = EsiClient(eve_character).get_active_fleet()
        if not esi_response.success():
            if not esi_response.data:
                msg = f"ESI error {esi_response.response_code} starting fleet {self.id}"
            elif "Character is not in a fleet" in esi_response.data["error"]:
                msg = f"Character {eve_character.character_name} not in a fleet (starting fleet {self.id})"
            else:
                msg = f"ESI error {esi_response.response_code} starting fleet {self.id}, {esi_response.data}"
            raise RuntimeError(msg)

        response = esi_response.data

        if EveFleetInstance.objects.filter(id=response["fleet_id"]).exists():
            fleet_instance = EveFleetInstance.objects.get(
                id=response["fleet_id"]
            )
            fleet_instance.eve_fleet = self
            fleet_instance.boss_id = response["fleet_boss_id"]
            fleet_instance.save()
        else:
            fleet_instance = EveFleetInstance.objects.create(
                id=response["fleet_id"],
                boss_id=response["fleet_boss_id"],
                eve_fleet=self,
            )

        fleet_instance.update_eve_fleet(self.disable_motd)

        if self.type != "strategic":
            doctrine = self.doctrine
        else:
            doctrine = None

        if self.audience.discord_channel_id:
            logger.info(
                "Sending fleet notification for fleet %s to discord channel %s",
                self.id,
                self.audience.discord_channel_id,
            )
            discord.create_message(
                self.audience.discord_channel_id,
                payload=get_fleet_discord_notification(
                    fleet_id=self.id,
                    fleet_type=self.get_type_display(),
                    fleet_location=self.location.location_name,
                    fleet_audience=self.audience.name,
                    fleet_commander_name=self.fleet_commander.character_name,
                    fleet_commander_id=self.fleet_commander.character_id,
                    fleet_description=self.description,
                    fleet_voice_channel=self.audience.discord_voice_channel_name,
                    fleet_voice_channel_link=self.audience.discord_voice_channel,
                    fleet_doctrine=doctrine,
                ),
            )

        if len(self.audience.evefleetaudiencewebhook_set.all()) > 0:
            for (
                audience_webhook
            ) in self.audience.evefleetaudiencewebhook_set.all():
                requests.post(
                    audience_webhook.webhook_url,
                    json=get_fleet_discord_notification(
                        fleet_id=self.id,
                        fleet_type=self.get_type_display(),
                        fleet_location=self.location.location_name,
                        fleet_audience=self.audience.name,
                        fleet_commander_name=self.fleet_commander.character_name,
                        fleet_commander_id=self.fleet_commander.character_id,
                        fleet_description=self.description,
                        fleet_voice_channel=self.audience.discord_voice_channel_name,
                        fleet_voice_channel_link=self.audience.discord_voice_channel,
                        fleet_doctrine=doctrine,
                    ),
                    timeout=2,
                )
        self.status = "active"
        self.save()


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
    boss_id = models.IntegerField(null=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    @property
    def active(self):
        return self.end_time is None

    def update_eve_fleet(self, disable_motd: bool):
        """Update fleet freemove and MOTD"""

        update = {
            "is_free_move": True,
        }

        if not disable_motd:
            self.motd = get_motd(
                self.eve_fleet.fleet_commander.character_id,
                self.eve_fleet.fleet_commander.character_name,
                self.eve_fleet.location.location_id,
                self.eve_fleet.location.location_name,
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
            update["motd"] = self.motd

        response = self.esi_client().update_fleet_details(self.id, update)

        if response.success():
            self.is_free_move = True
            self.save()
        else:
            logger.warning("Error updating Eve fleet %d", self.id)

    def _update_motd(self):
        """
        Update the motd for the fleet
        """

        motd = get_motd(
            self.eve_fleet.fleet_commander.character_id,
            self.eve_fleet.fleet_commander.character_name,
            self.eve_fleet.location.location_id,
            self.eve_fleet.location.location_name,
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
        if not self.eve_fleet.token:
            logger.warning(
                "Unable to set free move for fleet without token, %d",
                self.eve_fleet.id,
            )
            return None
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
        try:
            token = self.eve_fleet.token
            response = esi.client.Fleets.get_fleets_fleet_id(
                fleet_id=self.id, token=token
            ).results()

            self.is_registered = response["is_registered"]
            self.save()
            return response
        except Exception as e:
            # Don't need to handle this one gracefully
            logger.warning(
                "ESI call failed getting fleet registered status, %d %s",
                self.eve_fleet.id,
                e,
            )

    def esi_client(self):
        if self.boss_id:
            char_id = self.boss_id
        else:
            char_id = user_primary_character(
                self.eve_fleet.created_by
            ).character_id
        return EsiClient(char_id)

    def update_fleet_members(self):
        """
        Fetch the fleet members for the fleet
        """
        logger.info(
            "Updating members for fleet %d (%s)", self.eve_fleet.id, self.id
        )

        response = self.esi_client().get_fleet_members(self.id)
        if response.success():
            response = response.results()
        else:
            self.handle_fleet_update_esi_failure(response)
            return

        logger.info(
            "Fleet member count %d = %d ", self.eve_fleet.id, len(response)
        )

        ids_to_resolve = set()
        for esi_fleet_member in response:
            ids_to_resolve.add(esi_fleet_member["character_id"])
            ids_to_resolve.add(esi_fleet_member["ship_type_id"])
            ids_to_resolve.add(esi_fleet_member["solar_system_id"])
        ids_to_resolve = list(ids_to_resolve)
        resolved_ids = (
            EsiClient(None).resolve_universe_names(ids_to_resolve).results()
        )
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

        self.last_updated = timezone.now()
        self.save()

    def handle_fleet_update_esi_failure(self, esi_response):
        logger.warning(
            "ESI error updating fleet %d: %s (%d)",
            self.eve_fleet.id,
            esi_response.response,
            esi_response.response_code,
        )
        tries = 0
        max_tries = 8
        for member in EveFleetInstanceMember.objects.filter(
            eve_fleet_instance=self
        ):
            # Find an active member who can report who is now boss
            response = EsiClient(member.character_id).get_active_fleet()
            if response.success():
                # Make sure they are in the correct fleet
                if response.data["fleet_id"] == self.id:
                    # Update boss for future ESI calls
                    self.boss_id = response.data["fleet_boss_id"]
                    self.save()
                    logger.info(
                        "Updated fleet boss %d %d",
                        self.eve_fleet.id,
                        self.boss_id,
                    )
                    return
                else:
                    logger.info(
                        "Character no longer in same fleet %d, %d",
                        self.eve_fleet.id,
                        member.character_id,
                    )

            logger.info(
                "Fleet member no longer has access to fleet, char: %d fleet: %d status: %d",
                member.character_id,
                self.eve_fleet.id,
                response.response_code,
            )

            tries += 1
            if tries >= max_tries:
                break

        logger.info(
            "Closing fleet %d after %d attempts to find new boss",
            self.eve_fleet.id,
            tries,
        )
        self.end_time = timezone.now()
        self.save()

        self.eve_fleet.status = "complete"
        self.eve_fleet.save()


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
    squad_id = models.BigIntegerField()
    station_id = models.BigIntegerField(null=True, blank=True)
    takes_fleet_warp = models.BooleanField(default=False)
    wing_id = models.BigIntegerField()


class EveFleetLocation(models.Model):
    location_id = models.BigIntegerField(primary_key=True)
    location_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)

    def __str__(self):
        return str(f"{self.location_name}")


class EveFleetAudience(models.Model):
    """
    Used to scope fleets to a specific audience
    """

    name = models.CharField(max_length=255)
    groups = models.ManyToManyField(Group, blank=True)
    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    discord_channel_name = models.CharField(
        max_length=255, null=True, blank=True
    )
    discord_voice_channel_name = models.CharField(
        max_length=255, null=True, blank=True
    )
    discord_voice_channel = models.CharField(
        max_length=255, null=True, blank=True
    )
    add_to_schedule = models.BooleanField(default=True)
    hidden = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)


class EveFleetAudienceWebhook(models.Model):
    webhook_url = models.CharField(max_length=255)
    audience = models.ForeignKey(EveFleetAudience, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.webhook_url)


class EveStandingFleet(models.Model):
    """
    Representation of a standing fleet, a type of fleet that
    should always be available
    """

    start_time = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(null=True, blank=True)
    last_commander_change = models.DateTimeField(auto_now=True)
    external_fleet_id = models.BigIntegerField()

    active_fleet_commander_character_id = models.BigIntegerField()
    active_fleet_commander_character_name = models.CharField(max_length=255)

    @property
    def fleet_commander(self):
        return EveCharacter.objects.get(
            character_id=self.active_fleet_commander_character_id
        )

    @staticmethod
    def start(fleet_commander_character_id: int):
        """
        Start a standing fleet
        """
        eve_character = EveCharacter.objects.get(
            character_id=fleet_commander_character_id
        )
        token = eve_character.token.valid_access_token()

        response = esi.client.Fleets.get_characters_character_id_fleet(
            character_id=eve_character.character_id,
            token=token,
        ).results()

        if EveStandingFleet.objects.filter(
            external_fleet_id=response["fleet_id"]
        ).exists():
            existing_fleet = EveStandingFleet.objects.get(
                external_fleet_id=response["fleet_id"]
            )
            existing_fleet.active_fleet_commander_character_id = (
                fleet_commander_character_id
            )
            existing_fleet.active_fleet_commander_character_name = (
                eve_character.character_name
            )
            existing_fleet.end_time = None
            existing_fleet.save()
        else:
            return EveStandingFleet.objects.create(
                external_fleet_id=response["fleet_id"],
                active_fleet_commander_character_id=fleet_commander_character_id,
                active_fleet_commander_character_name=eve_character.character_name,
            )

    def claim(self, character_id):
        """
        Claim the standing fleet
        """
        # attempt to get fleet members
        # if fails, they are not valid to claim
        token = EveCharacter.objects.get(
            character_id=character_id
        ).token.valid_access_token()
        new_fleet_commander = EveCharacter.objects.get(
            character_id=character_id
        )
        old_fleet_commander = self.fleet_commander
        try:
            esi.client.Fleets.get_fleets_fleet_id_members(
                fleet_id=self.external_fleet_id,
                token=token,
            ).results()

            EveStandingFleetCommanderLog.objects.create(
                eve_standing_fleet=self,
                character_id=old_fleet_commander.character_id,
                character_name=old_fleet_commander.character_name,
                start_time=self.last_commander_change,
                leave_time=timezone.now(),
            )
            self.active_fleet_commander_character_id = (
                new_fleet_commander.character_id
            )
            self.active_fleet_commander_character_name = (
                new_fleet_commander.character_name
            )
            self.end_time = None
            self.last_commander_change = timezone.now()
            self.save()
            return True
        except Exception:
            return False

    def update_members(self):
        """
        Update the members of the standing fleet
        - Add new standing fleet members
        - Delete old standing fleet members and create a log record
        """
        token = self.fleet_commander.token.valid_access_token()
        response = esi.client.Fleets.get_fleets_fleet_id_members(
            fleet_id=self.external_fleet_id,
            token=token,
        ).results()

        ids_to_resolve = set()
        for esi_fleet_member in response:
            ids_to_resolve.add(esi_fleet_member["character_id"])
        ids_to_resolve = list(ids_to_resolve)
        resolved_ids = esi.client.Universe.post_universe_names(
            ids=ids_to_resolve
        ).results()
        resolved_ids = {x["id"]: x["name"] for x in resolved_ids}

        for esi_fleet_member in response:
            if not EveStandingFleetMember.objects.filter(
                eve_standing_fleet=self,
                character_id=esi_fleet_member["character_id"],
            ).exists():
                EveStandingFleetMember.objects.create(
                    eve_standing_fleet=self,
                    character_id=esi_fleet_member["character_id"],
                    character_name=resolved_ids[
                        esi_fleet_member["character_id"]
                    ],
                )

        for fleet_member in EveStandingFleetMember.objects.filter(
            eve_standing_fleet=self
        ):
            if not any(
                x["character_id"] == fleet_member.character_id
                for x in response
            ):
                EveStandingFleetMemberLog.objects.create(
                    eve_standing_fleet=self,
                    character_id=fleet_member.character_id,
                    character_name=fleet_member.character_name,
                    leave_time=timezone.now(),
                )
                fleet_member.delete()


class EveStandingFleetCommanderLog(models.Model):
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    join_time = models.DateTimeField(auto_now_add=True)
    leave_time = models.DateTimeField(null=True, blank=True)
    eve_standing_fleet = models.ForeignKey(
        EveStandingFleet, on_delete=models.CASCADE
    )


class EveStandingFleetMember(models.Model):

    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    eve_standing_fleet = models.ForeignKey(
        EveStandingFleet, on_delete=models.CASCADE
    )


class EveStandingFleetMemberLog(models.Model):
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    join_time = models.DateTimeField(auto_now_add=True)
    leave_time = models.DateTimeField(null=True, blank=True)
    eve_standing_fleet = models.ForeignKey(
        EveStandingFleet, on_delete=models.CASCADE
    )
