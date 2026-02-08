import logging

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils import timezone

from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveLocation
from eveonline.helpers.characters import user_primary_character
from fittings.models import EveDoctrine
from fleets.motd import get_motd
from fleets.notifications import get_fleet_discord_notification

discord = DiscordClient()
logger = logging.getLogger(__name__)


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
        help_text="DEPRECATED: Use audience.staging_location instead. Kept for data migration purposes.",
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
        """
        Get the formup location for the fleet.
        Prefers audience.staging_location over the deprecated location field.
        """
        if self.audience and self.audience.staging_location:
            return self.audience.staging_location
        return self.location

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

        self.status = "active"
        self.save()

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
            formup_location = self.eve_fleet.formup_location
            role_volunteers = _motd_role_volunteers(self.eve_fleet)
            missing_roles = _motd_missing_roles(self.eve_fleet)
            volunteer_url = (
                _motd_volunteer_url(self.eve_fleet) if missing_roles else None
            )
            self.motd = get_motd(
                self.eve_fleet.fleet_commander.character_id,
                self.eve_fleet.fleet_commander.character_name,
                formup_location.location_id if formup_location else None,
                formup_location.short_name if formup_location else None,
                "https://discord.gg/minmatar",
                "Minmatar Fleet Discord",
                (
                    self.eve_fleet.doctrine.doctrine_link
                    if self.eve_fleet.doctrine
                    else None
                ),
                (
                    self.eve_fleet.doctrine.name
                    if self.eve_fleet.doctrine
                    else None
                ),
                role_volunteers=role_volunteers,
                missing_roles=missing_roles or None,
                volunteer_url=volunteer_url,
            )
            update["motd"] = self.motd

        response = self.esi_client().update_fleet_details(self.id, update)

        if response.success():
            self.is_free_move = True
            self.save()
        else:
            logger.warning("Error updating Eve fleet %d", self.id)

    def refresh_motd(self):
        """Regenerate and push the fleet MOTD to ESI. Public API for callers."""
        return self._update_motd()

    def _update_motd(self):
        """Update the motd for the fleet and push to ESI."""
        formup_location = self.eve_fleet.formup_location
        role_volunteers = _motd_role_volunteers(self.eve_fleet)
        missing_roles = _motd_missing_roles(self.eve_fleet)
        volunteer_url = (
            _motd_volunteer_url(self.eve_fleet) if missing_roles else None
        )
        motd = get_motd(
            self.eve_fleet.fleet_commander.character_id,
            self.eve_fleet.fleet_commander.character_name,
            formup_location.location_id if formup_location else None,
            formup_location.short_name if formup_location else None,
            "https://discord.gg/minmatar",
            "Minmatar Fleet Discord",
            (
                self.eve_fleet.doctrine.doctrine_link
                if self.eve_fleet.doctrine
                else None
            ),
            self.eve_fleet.doctrine.name if self.eve_fleet.doctrine else None,
            role_volunteers=role_volunteers,
            missing_roles=missing_roles or None,
            volunteer_url=volunteer_url,
        )
        # token = self.eve_fleet.token
        update = {"motd": motd}
        response = (
            EsiClient(self.eve_fleet.fleet_commander)
            .update_fleet_details(self.id, update)
            .results()
        )
        # response = esi.client.Fleets.put_fleets_fleet_id(
        #     fleet_id=self.id, new_settings={"motd": motd}, token=token
        # ).results()
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
        # token = self.eve_fleet.token
        # response = esi.client.Fleets.put_fleets_fleet_id(
        #     fleet_id=self.id,
        #     new_settings={"is_free_move": True},
        #     token=token,
        # ).results()
        update = {"is_free_move": True}
        response = (
            self.esi_client().update_fleet_details(self.id, update).results()
        )

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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["character_id"]),
        ]


class EveFleetInstanceMemberRole(models.Model):
    """
    Optional role assigned to a fleet instance member for critical fleet positions.
    Roles: Logi Anchor, DPS Anchor, Links, Cyno, Scout.
    For roles that need extra coordination (e.g. Links), use the optional RoleDetail.
    """

    ROLE_LOGI_ANCHOR = "logi_anchor"
    ROLE_DPS_ANCHOR = "dps_anchor"
    ROLE_LINKS = "links"
    ROLE_CYNO = "cyno"
    ROLE_SCOUT = "scout"

    ROLE_CHOICES = (
        (ROLE_LOGI_ANCHOR, "Logi Anchor"),
        (ROLE_DPS_ANCHOR, "DPS Anchor"),
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
    (e.g. Links: subtype shield/armor/info/skirmish; quantity for slot counts).
    """

    SUBTYPE_ARMOR = "armor"
    SUBTYPE_SHIELD = "shield"
    SUBTYPE_INFO = "info"
    SUBTYPE_SKIRMISH = "skirmish"

    SUBTYPE_CHOICES = (
        (SUBTYPE_ARMOR, "Armor"),
        (SUBTYPE_SHIELD, "Shield"),
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
        help_text="Optional; e.g. armor, shield, info, skirmish for roles that need it.",
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
    ROLE_DPS_ANCHOR = "dps_anchor"
    ROLE_LINKS = "links"
    ROLE_CYNO = "cyno"
    ROLE_SCOUT = "scout"

    ROLE_CHOICES = (
        (ROLE_LOGI_ANCHOR, "Logi Anchor"),
        (ROLE_DPS_ANCHOR, "DPS Anchor"),
        (ROLE_LINKS, "Links"),
        (ROLE_CYNO, "Cyno"),
        (ROLE_SCOUT, "Scout"),
    )

    SUBTYPE_ARMOR = "armor"
    SUBTYPE_SHIELD = "shield"
    SUBTYPE_INFO = "info"
    SUBTYPE_SKIRMISH = "skirmish"

    SUBTYPE_CHOICES = (
        (SUBTYPE_ARMOR, "Armor"),
        (SUBTYPE_SHIELD, "Shield"),
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


def _motd_role_volunteers(eve_fleet):
    """Build role_volunteers list for get_motd: Logi Anchor, DPS Anchor, Cynos."""
    critical_roles = [
        (EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR, "Logi Anchor"),
        (EveFleetRoleVolunteer.ROLE_DPS_ANCHOR, "DPS Anchor"),
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


def _motd_missing_roles(eve_fleet):
    """
    Required: all 4 link subtypes, 1 logi anchor, 1 dps anchor, at least 2 cynos.
    Return list of short strings for MOTD, e.g. ["Logi Anchor", "Links (Armor)", "1 more Cyno"].
    """
    missing = []

    # Links: need at least one volunteer per subtype (armor, shield, info, skirmish)
    link_subtype_labels = {
        EveFleetRoleVolunteer.SUBTYPE_ARMOR: "Armor",
        EveFleetRoleVolunteer.SUBTYPE_SHIELD: "Shield",
        EveFleetRoleVolunteer.SUBTYPE_INFO: "Info",
        EveFleetRoleVolunteer.SUBTYPE_SKIRMISH: "Skirmish",
    }
    links_with_subtype = set(
        EveFleetRoleVolunteer.objects.filter(
            eve_fleet=eve_fleet,
            role=EveFleetRoleVolunteer.ROLE_LINKS,
            subtype__isnull=False,
        )
        .exclude(subtype="")
        .values_list("subtype", flat=True)
    )
    for subtype_value, label in link_subtype_labels.items():
        if subtype_value not in links_with_subtype:
            missing.append(f"Links ({label})")

    # Logi anchor: need at least 1
    if not EveFleetRoleVolunteer.objects.filter(
        eve_fleet=eve_fleet, role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR
    ).exists():
        missing.append("Logi Anchor")

    # DPS anchor: need at least 1
    if not EveFleetRoleVolunteer.objects.filter(
        eve_fleet=eve_fleet, role=EveFleetRoleVolunteer.ROLE_DPS_ANCHOR
    ).exists():
        missing.append("DPS Anchor")

    # Cynos: need at least 2
    cyno_count = EveFleetRoleVolunteer.objects.filter(
        eve_fleet=eve_fleet, role=EveFleetRoleVolunteer.ROLE_CYNO
    ).count()
    if cyno_count < 2:
        if cyno_count == 0:
            missing.append("2 Cynos")
        else:
            missing.append("1 more Cyno")

    return missing


def _motd_volunteer_url(eve_fleet):
    """URL to the fleet volunteer page for MOTD."""
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    return f"{base.rstrip('/')}/fleets/upcoming/{eve_fleet.id}/volunteer"


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
    staging_location = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
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
