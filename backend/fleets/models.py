import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils import timezone

from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveLocation
from eveonline.helpers.characters import user_primary_character
from fittings.models import EveDoctrine, EveFitting, EveFittingRefit
from fleets.helpers.member_ships import apply_esi_fleet_member
from fleets.helpers.eft_items import fitting_href
from fleets.motd import get_motd
from fleets.notifications import get_fleet_discord_notification

discord = DiscordClient()
logger = logging.getLogger(__name__)

# ESI rejects fleet MOTDs longer than this (characters).
MOTD_MAX_LENGTH = 4000


class EveFleet(models.Model):
    """
    Model for storing a fleet in our database
    """

    fleet_types = (
        ("strategic", "Strategic Operation"),
        ("non_strategic", "Non Strategic Operation"),
        ("training", "Training Operation"),
        ("npsi", "NPSI"),
    )
    description = models.TextField(blank=True)
    objective = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Short tagline for the fleet (one sentence).",
    )
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

    # Link to After Action Report in Discord
    # e.g. https://discord.com/channels/1041384161505722368/1398825964225695945
    aar_link = models.CharField(max_length=120, null=True)
    roam_report_url = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @property
    def token(self):
        if self.fleet_commander and self.fleet_commander.token:
            return self.fleet_commander.token.valid_access_token()
        else:
            return None

    @property
    def fleet_commander(self):
        return user_primary_character(self.created_by)

    @property
    def formup_location(self):
        """Get the formup location for the fleet."""
        return self.location

    def __str__(self):
        return f"{self.created_by} - {self.type} - {self.start_time}"

    def generate_esi_fleet(
        self, character_id: int | None = None
    ) -> "EveFleetInstance":
        """
        Resolve the FC's active fleet from ESI, create or update EveFleetInstance,
        and update in-game fleet (freemove, MOTD). Returns the fleet instance.
        """
        logger.info("Generating ESI fleet for fleet %s", self.id)

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

        # Only the in-game fleet boss (fleet commander) may link/start tracking.
        # Otherwise a member can "steal" an existing EveFleetInstance.
        if response.get("fleet_boss_id") != eve_character.character_id:
            raise RuntimeError(
                f"Character {eve_character.character_name} is not the fleet "
                f"commander (starting fleet {self.id})"
            )

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
        return fleet_instance

    def notify_discord(self) -> None:
        """
        Send the fleet notification to the audience's Discord channel, if configured.
        """
        if not self.audience or not self.audience.discord_channel_id:
            return

        doctrine = None if self.type == "strategic" else self.doctrine
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
                fleet_location=(
                    self.formup_location.location_name
                    if self.formup_location
                    else "Ask FC"
                ),
                fleet_audience=self.audience.name,
                fleet_commander_name=self.fleet_commander.character_name,
                fleet_commander_id=self.fleet_commander.character_id,
                fleet_description=self.description,
                fleet_voice_channel=None,
                fleet_voice_channel_link=None,
                fleet_doctrine=doctrine,
            ),
        )

    def activate(self) -> None:
        """Mark the fleet as active and persist."""
        self.status = "active"
        self.save()

    def start(self, character_id: int | None = None) -> None:
        """
        Start the fleet: link to ESI fleet, optionally notify Discord, mark active.
        """
        logger.info("Starting fleet %s", self.id)
        self.generate_esi_fleet(character_id)
        self.notify_discord()
        self.activate()

    class Meta:
        indexes = [
            models.Index(fields=["start_time"]),
        ]


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
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @property
    def active(self):
        return self.end_time is None

    def update_eve_fleet(self, disable_motd: bool):
        """Update fleet freemove and MOTD"""

        update = {
            "is_free_move": True,
        }

        if not disable_motd:
            self.motd = self.build_motd()
            update["motd"] = self.motd

        response = self.esi_client().update_fleet_details(self.id, update)

        if response.success():
            self.is_free_move = True
            self.save()
        else:
            logger.warning(
                "Error updating Eve fleet %d: %s (%s)",
                self.id,
                response.response,
                response.response_code,
            )

    def refresh_motd(self):
        """Regenerate and push the fleet MOTD to ESI. Public API for callers."""
        return self._update_motd()

    def build_motd(self) -> str:
        """Compose the MOTD text from the fleet's current state (no ESI)."""
        eve_fleet = self.eve_fleet
        formup_location = eve_fleet.formup_location
        kwargs = {
            "role_volunteers": _motd_role_volunteers(eve_fleet),
            "fleet_edit_url": _motd_fleet_edit_url(eve_fleet),
            "refits": _motd_refits(eve_fleet),
            "composition": _motd_composition(eve_fleet),
        }
        args = (
            eve_fleet.fleet_commander.character_id,
            eve_fleet.fleet_commander.character_name,
            formup_location.location_id if formup_location else None,
            formup_location.short_name if formup_location else None,
            "https://discord.gg/minmatar",
            "Minmatar Fleet Discord",
            eve_fleet.doctrine.doctrine_link if eve_fleet.doctrine else None,
            eve_fleet.doctrine.name if eve_fleet.doctrine else None,
        )
        motd = get_motd(*args, **kwargs)
        # ESI caps the MOTD length; drop the refit section first.
        if len(motd) > MOTD_MAX_LENGTH and kwargs["refits"]:
            kwargs["refits"] = []
            motd = get_motd(*args, **kwargs)
        # In-game DNA links are long; fall back to web links / plain names.
        if len(motd) > MOTD_MAX_LENGTH and kwargs["composition"]:
            kwargs["composition"] = _motd_composition(eve_fleet, in_game=False)
            motd = get_motd(*args, **kwargs)
        return motd

    def _update_motd(self):
        """Update the motd for the fleet and push to ESI."""
        motd = self.build_motd()
        update = {"motd": motd}
        response = self.esi_client().update_fleet_details(self.id, update)
        if not response.success():
            raise ValueError(
                f"Cannot return data for failed ESI call ({response.response_code}): "
                f"{response.response}"
            )
        self.motd = motd
        self.save()
        return response.results() if response.data is not None else None

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
        # token = self.eve_fleet.token
        # response = esi.client.Fleets.put_fleets_fleet_id(
        #     fleet_id=self.id,
        #     new_settings={"is_free_move": True},
        #     token=token,
        # ).results()
        update = {"is_free_move": True}
        response = self.esi_client().update_fleet_details(self.id, update)
        if not response.success():
            logger.warning(
                "Error setting free move for fleet %d: %s (%s)",
                self.id,
                response.response,
                response.response_code,
            )
            return None
        response = response.results() if response.data is not None else None

        self.is_free_move = True
        self.save()
        return response

    def update_is_registered_status(self):
        """
        Fetch the advert status for the fleet
        """
        try:
            # token = self.eve_fleet.token
            # response = esi.client.Fleets.get_fleets_fleet_id(
            #     fleet_id=self.id, token=token
            # ).results()
            response = self.esi_client().get_fleet(self.id).results()

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
            apply_esi_fleet_member(self, esi_fleet_member, resolved_ids)

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

        min_open = self.start_time + timedelta(hours=1)
        if timezone.now() < min_open:
            logger.info(
                "Skipping auto-close for fleet %d: instance open < 1 hour "
                "(boss recovery exhausted after %d tries)",
                self.eve_fleet.id,
                tries,
            )
            return

        logger.info(
            "Closing fleet %d after %d attempts to find new boss",
            self.eve_fleet.id,
            tries,
        )
        self.end_time = timezone.now()
        self.save()

        self.eve_fleet.status = "complete"
        self.eve_fleet.save()
        close_fleet_cleanup(self.eve_fleet)
        # Imported lazily: fleets.helpers.roam_report may import this module.
        from fleets.helpers.roam_report import (  # pylint: disable=import-outside-toplevel
            schedule_roam_report,
        )

        schedule_roam_report(self.eve_fleet.id)


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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["character_id"]),
        ]


class EveFleetInstanceMemberImplantSnapshot(models.Model):
    """Append-only record of a fleet member's active implants at poll time."""

    member = models.ForeignKey(
        EveFleetInstanceMember,
        on_delete=models.CASCADE,
        related_name="implant_snapshots",
    )
    implants = models.JSONField(default=dict, blank=True)
    estimated_value_isk = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["member", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.member.character_name} @ {self.created_at:%Y-%m-%d %H:%M}"
        )


class EveFleetInstanceMemberShipSnapshot(models.Model):
    """Append-only record of a fleet member's ship at each observed change."""

    member = models.ForeignKey(
        EveFleetInstanceMember,
        on_delete=models.CASCADE,
        related_name="ship_snapshots",
    )
    ship_type_id = models.BigIntegerField()
    ship_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["member", "created_at"]),
            models.Index(fields=["member", "ship_type_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.member.character_name} — {self.ship_name} "
            f"@ {self.created_at:%Y-%m-%d %H:%M}"
        )


class EveFleetInstanceMemberRole(models.Model):
    """
    Optional role assigned to a fleet instance member for critical fleet positions.
    Roles: Logi FC, Links, Cyno, Scout.
    For roles that need extra coordination (e.g. Links), use the optional RoleDetail.
    """

    ROLE_LOGI_ANCHOR = "logi_anchor"
    ROLE_LINKS = "links"
    ROLE_CYNO = "cyno"
    ROLE_SCOUT = "scout"

    ROLE_CHOICES = (
        (ROLE_LOGI_ANCHOR, "Logi FC"),
        (ROLE_LINKS, "Links"),
        (ROLE_CYNO, "Cyno"),
        (ROLE_SCOUT, "Scout"),
    )

    eve_fleet_instance_member = models.ForeignKey(
        EveFleetInstanceMember,
        on_delete=models.CASCADE,
        related_name="filled_roles",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["eve_fleet_instance_member", "role"],
                name="fleets_member_role_unique",
            )
        ]
        indexes = [
            models.Index(fields=["eve_fleet_instance_member", "role"]),
        ]

    def __str__(self):
        parts = [
            self.eve_fleet_instance_member.character_name,
            self.get_role_display(),
        ]
        try:
            detail = self.detail
            if detail.subtype:
                parts.append(f"({detail.get_subtype_display()})")
            if detail.quantity is not None:
                parts.append(f"×{detail.quantity}")
        except EveFleetInstanceMemberRoleDetail.DoesNotExist:
            pass
        return " — ".join(parts)


class EveFleetInstanceMemberRoleDetail(models.Model):
    """
    Optional detail for a fleet member role when the role needs extra coordination
    (e.g. Links: subtype ehp/info/skirmish; quantity for slot counts).
    """

    SUBTYPE_EHP = "ehp"
    SUBTYPE_INFO = "info"
    SUBTYPE_SKIRMISH = "skirmish"

    SUBTYPE_CHOICES = (
        (SUBTYPE_EHP, "EHP"),
        (SUBTYPE_INFO, "Info"),
        (SUBTYPE_SKIRMISH, "Skirmish"),
    )

    eve_fleet_instance_member_role = models.OneToOneField(
        EveFleetInstanceMemberRole,
        on_delete=models.CASCADE,
        related_name="detail",
    )
    subtype = models.CharField(
        max_length=16,
        choices=SUBTYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Optional; e.g. ehp, info, skirmish for roles that need it.",
    )
    quantity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional; for roles that need a count (e.g. link slots).",
    )

    def __str__(self):
        parts = [str(self.eve_fleet_instance_member_role)]
        if self.subtype:
            parts.append(self.get_subtype_display())
        if self.quantity is not None:
            parts.append(f"×{self.quantity}")
        return " — ".join(parts)


class EveFleetRoleVolunteer(models.Model):
    """
    User volunteers a character for a fleet role (upcoming fleet).
    Same role choices as EveFleetInstanceMemberRole; optional subtype/quantity for coordination.
    """

    ROLE_LOGI_ANCHOR = "logi_anchor"
    ROLE_LINKS = "links"
    ROLE_CYNO = "cyno"
    ROLE_SCOUT = "scout"

    ROLE_CHOICES = (
        (ROLE_LOGI_ANCHOR, "Logi FC"),
        (ROLE_LINKS, "Links"),
        (ROLE_CYNO, "Cyno"),
        (ROLE_SCOUT, "Scout"),
    )

    SUBTYPE_EHP = "ehp"
    SUBTYPE_INFO = "info"
    SUBTYPE_SKIRMISH = "skirmish"

    SUBTYPE_CHOICES = (
        (SUBTYPE_EHP, "EHP"),
        (SUBTYPE_INFO, "Info"),
        (SUBTYPE_SKIRMISH, "Skirmish"),
    )

    eve_fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="role_volunteers"
    )
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    subtype = models.CharField(
        max_length=16,
        choices=SUBTYPE_CHOICES,
        null=True,
        blank=True,
    )
    quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    # FC-assigned system for cyno volunteers. Private: never shown in the
    # MOTD; only the FC and the volunteer see it, and the pilot gets a DM.
    solar_system_id = models.BigIntegerField(null=True, blank=True)
    solar_system_name = models.CharField(
        max_length=255, blank=True, default=""
    )

    class Meta:
        """Unique per fleet/character/role; default ordering for display."""

        constraints = [
            models.UniqueConstraint(
                fields=["eve_fleet", "character_id", "role"],
                name="fleets_role_volunteer_unique",
            )
        ]
        indexes = [
            models.Index(fields=["eve_fleet"]),
        ]
        ordering = ["eve_fleet", "role", "id"]

    def __str__(self):
        return f"{self.character_name} — {self.get_role_display()}"


class EveFleetFitting(models.Model):
    """
    One ship in a fleet's ad-hoc composition. Lets an FC build a "makeshift
    doctrine" from catalog fittings (``fitting`` set) or run something
    completely different by pasting EFT (``eft_format`` set, ``fitting``
    null). Merged with the doctrine's fittings when the fleet has one.
    """

    ROLE_CHOICES = (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("support", "Support"),
    )

    eve_fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="fleet_fittings"
    )
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fleet_fittings",
        help_text="Catalog fitting; leave empty for a manual EFT fit.",
    )
    name = models.CharField(max_length=255)
    ship_id = models.IntegerField()
    eft_format = models.TextField(
        blank=True,
        default="",
        help_text="EFT block for manual fits (ignored for catalog fits).",
    )
    role = models.CharField(
        max_length=16, choices=ROLE_CHOICES, default="primary"
    )
    order = models.PositiveSmallIntegerField(default=0)
    # In-game saved fitting created under the FC for manual fits, removed
    # when the fleet closes (see fleets.helpers.esi_fittings).
    esi_fitting_id = models.BigIntegerField(null=True, blank=True)
    esi_character_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        # A catalog fit may appear once per fleet; enforced in the create
        # endpoint because MariaDB ignores conditional unique constraints.
        indexes = [
            models.Index(fields=["eve_fleet"]),
        ]
        ordering = ["eve_fleet", "order", "id"]

    @property
    def is_manual(self) -> bool:
        return self.fitting_id is None

    @property
    def effective_eft(self) -> str:
        if self.fitting_id:
            return self.fitting.eft_format
        return self.eft_format

    def __str__(self):
        return f"{self.eve_fleet_id} — {self.name}"


class EveFleetShipVolunteer(models.Model):
    """
    User volunteers a character to fly one of the fittings in the fleet's
    composition (doctrine or fleet fitting) for an upcoming fleet.
    Exactly one of ``fitting`` / ``fleet_fitting`` is set.
    """

    eve_fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="ship_volunteers"
    )
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fleet_ship_volunteers",
    )
    fleet_fitting = models.ForeignKey(
        EveFleetFitting,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ship_volunteers",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["eve_fleet", "character_id", "fitting"],
                name="fleets_ship_volunteer_unique",
            ),
            models.UniqueConstraint(
                fields=["eve_fleet", "character_id", "fleet_fitting"],
                name="fleets_ship_volunteer_fleet_fitting_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(fitting__isnull=False, fleet_fitting__isnull=True)
                    | models.Q(
                        fitting__isnull=True, fleet_fitting__isnull=False
                    )
                ),
                name="fleets_ship_volunteer_one_target",
            ),
        ]
        indexes = [
            models.Index(fields=["eve_fleet"]),
        ]
        ordering = ["eve_fleet", "fitting", "fleet_fitting", "id"]

    @property
    def target_name(self) -> str:
        return (
            self.fitting.name if self.fitting_id else self.fleet_fitting.name
        )

    @property
    def target_ship_id(self) -> int:
        return (
            self.fitting.ship_id
            if self.fitting_id
            else self.fleet_fitting.ship_id
        )

    def __str__(self):
        return f"{self.character_name} — {self.target_name}"


class EveFleetFittingRefit(models.Model):
    """
    FC-configured refit for one of the fleet's doctrine fittings: what pilots
    should carry in their cargohold so the fit can be swapped in-fleet.
    Optionally points at a curated EveFittingRefit; cargo_modules is the
    editable list of modules to bring (one per line, ``Name xN``).
    """

    eve_fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="refits"
    )
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fleet_refits",
    )
    fleet_fitting = models.ForeignKey(
        EveFleetFitting,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="refits",
    )
    refit = models.ForeignKey(
        EveFittingRefit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_refits",
    )
    name = models.CharField(max_length=255)
    cargo_modules = models.TextField(
        blank=True,
        default="",
        help_text="Modules to carry in cargo, one per line (``Name xN``).",
    )
    notes = models.CharField(max_length=200, blank=True, default="")
    eft_format = models.TextField(
        blank=True,
        default="",
        help_text="Full EFT of the refitted ship (for in-game links).",
    )
    esi_fitting_id = models.BigIntegerField(null=True, blank=True)
    esi_character_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["eve_fleet", "fitting", "name"],
                name="fleets_refit_unique",
            ),
            models.UniqueConstraint(
                fields=["eve_fleet", "fleet_fitting", "name"],
                name="fleets_refit_fleet_fitting_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(fitting__isnull=False, fleet_fitting__isnull=True)
                    | models.Q(
                        fitting__isnull=True, fleet_fitting__isnull=False
                    )
                ),
                name="fleets_refit_one_target",
            ),
        ]
        indexes = [
            models.Index(fields=["eve_fleet"]),
        ]
        ordering = ["eve_fleet", "fitting", "fleet_fitting", "id"]

    @property
    def target_name(self) -> str:
        return (
            self.fitting.name if self.fitting_id else self.fleet_fitting.name
        )

    @property
    def target_ship_id(self) -> int:
        return (
            self.fitting.ship_id
            if self.fitting_id
            else self.fleet_fitting.ship_id
        )

    @property
    def base_eft(self) -> str:
        return (
            self.fitting.eft_format
            if self.fitting_id
            else self.fleet_fitting.effective_eft
        )

    def __str__(self):
        return f"{self.target_name} → {self.name}"


def _motd_role_volunteers(eve_fleet):
    """
    Build role_volunteers list for get_motd: Logi FC, Cynos.
    The FC-assigned cyno system is intentionally NOT included: it is
    private and delivered to the pilot by Discord DM.
    """
    critical_roles = [
        (EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR, "Logi FC"),
        (EveFleetRoleVolunteer.ROLE_CYNO, "Cynos"),
    ]
    result = []
    for role_value, role_label in critical_roles:
        volunteers = EveFleetRoleVolunteer.objects.filter(
            eve_fleet=eve_fleet, role=role_value
        ).order_by("id")
        result.append(
            (
                role_label,
                [(v.character_id, v.character_name) for v in volunteers],
            )
        )
    return result


def close_fleet_cleanup(eve_fleet) -> None:
    """Housekeeping when a fleet ends: drop the in-game fittings we saved."""
    from fleets.helpers.esi_fittings import (  # pylint: disable=import-outside-toplevel
        cleanup_fleet_esi_fittings,
    )

    try:
        cleanup_fleet_esi_fittings(eve_fleet)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(
            "ESI fitting cleanup failed for fleet %s: %s", eve_fleet.id, e
        )


def _motd_refits(eve_fleet):
    """
    Build refits list for get_motd: [(refit_name, refit_href)].
    refit_href is an in-game ``fitting:`` link when the refit EFT resolves.
    """
    refits = EveFleetFittingRefit.objects.filter(eve_fleet=eve_fleet)
    return [
        (
            refit.name,
            fitting_href(refit.eft_format) if refit.eft_format else None,
        )
        for refit in refits
    ]


def _fitting_web_url(fitting_id):
    """Public fitting page for a catalog fit; None for manual fits."""
    if not fitting_id:
        return None
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    return f"{base.rstrip('/')}/ships/fittings/{fitting_id}"


def _motd_composition(eve_fleet, in_game=True):
    """
    Fleet-specific fits for the MOTD when there is no doctrine: list of
    (name, href|None). Every fit opens in-game via a ``fitting:`` DNA link;
    catalog fits fall back to their web page when the hull is unknown or
    when ``in_game`` is off (MOTD too long).
    """
    if eve_fleet.doctrine_id:
        return []
    fittings = EveFleetFitting.objects.filter(eve_fleet=eve_fleet).order_by(
        "role", "order", "id"
    )
    return [
        (
            f.name,
            (fitting_href(f.effective_eft) if in_game else None)
            or _fitting_web_url(f.fitting_id),
        )
        for f in fittings
    ]


def _motd_fleet_edit_url(eve_fleet):
    """URL to the fleet edit page for MOTD."""
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    return f"{base.rstrip('/')}/fleets/upcoming/edit/{eve_fleet.id}"


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
    image_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="URL to the image to display for this fleet audience",
    )
    add_to_schedule = models.BooleanField(default=True)
    hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.name)


class NpsiEventSource(models.Model):
    """External NPSI calendar feed (e.g. Unaligned iCal JSON)."""

    name = models.CharField(max_length=100, unique=True)
    feed_url = models.URLField(max_length=500)
    fc_character_name = models.CharField(
        max_length=255,
        help_text="Fallback FC if the feed item has no character_name.",
    )
    default_audience = models.ForeignKey(
        EveFleetAudience,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Required before events can be posted to the schedule.",
    )
    default_type = models.CharField(
        max_length=32,
        choices=EveFleet.fleet_types,
        default="npsi",
    )
    default_location = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NPSI event source"

    def __str__(self):
        return self.name


class NpsiExternalEvent(models.Model):
    """One calendar occurrence from an NPSI feed."""

    class Status(models.TextChoices):
        SEEN = "seen", "Seen"
        NOTIFIED = "notified", "Notified"
        CREATED = "created", "Posted"
        SKIPPED = "skipped", "Skipped"

    source = models.ForeignKey(
        NpsiEventSource,
        on_delete=models.CASCADE,
        related_name="events",
    )
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    summary = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location_text = models.CharField(max_length=255, blank=True)
    character_name = models.CharField(max_length=255, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.SEEN,
    )
    skip_reason = models.CharField(max_length=255, blank=True)
    eve_fleet = models.ForeignKey(
        EveFleet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    discord_message_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NPSI external event"
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.summary} @ {self.start_time}"
