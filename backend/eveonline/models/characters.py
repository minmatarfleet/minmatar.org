import logging
from typing import List

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from esi.models import Token

from eveonline.models.alliances import EveAlliance

logger = logging.getLogger(__name__)


class EvePlayer(models.Model):
    """Represents an Eve Online player"""

    nickname = models.CharField(max_length=255, unique=True)
    primary_character = models.OneToOneField(
        "EveCharacter", on_delete=models.SET_NULL, null=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    prime_choices = (
        ("US", "US"),
        ("US_AP", "US / AP"),
        ("AP", "AP"),
        ("AP_EU", "AP / EU"),
        ("EU", "EU"),
        ("EU_US", "EU / US"),
    )
    prime_time = models.CharField(
        max_length=16, choices=prime_choices, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        user_name = self.user.username if self.user else "unknown"
        primary_char = (
            self.primary_character.character_name
            if self.primary_character
            else "unknown"
        )
        return f"{user_name} / {primary_char}"


class EveCharacter(models.Model):
    """Character model"""

    character_id = models.IntegerField(unique=True)
    character_name = models.CharField(max_length=255, blank=True)
    corporation_id = models.BigIntegerField(null=True, blank=True)
    alliance_id = models.BigIntegerField(null=True, blank=True)
    faction_id = models.BigIntegerField(null=True, blank=True)
    token = models.ForeignKey(
        Token, on_delete=models.SET_NULL, null=True, blank=True
    )
    exempt = models.BooleanField(default=False)
    esi_suspended = models.BooleanField(default=False)
    esi_token_level = models.CharField(max_length=40, null=True, blank=True)
    esi_scope_groups = models.JSONField(default=list, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.character_name)

    def summary(self):
        return f"{self.character_name} ({self.character_id})"

    @property
    def is_primary(self) -> bool:
        if not self.user:
            return False
        try:
            player = self.user.eveplayer
            return player.primary_character == self
        except EvePlayer.DoesNotExist:
            return False

    class Meta:
        indexes = [
            models.Index(fields=["character_name"]),
            models.Index(fields=["user"]),
        ]


class EveTag(models.Model):
    title = models.CharField(max_length=40, default="TBC")
    description = models.CharField(max_length=255)
    image_name = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterTag(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    tag = models.ForeignKey(EveTag, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (("character", "tag"),)


class EveCharacterLog(models.Model):
    username = models.CharField(max_length=255)
    character_name = models.CharField(max_length=255)
    added = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterSkill(models.Model):
    skill_id = models.IntegerField()
    skill_name = models.CharField(max_length=255)
    skill_points = models.IntegerField()
    skill_level = models.IntegerField()
    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterKillmail(models.Model):
    id = models.BigIntegerField(primary_key=True)
    killmail_id = models.BigIntegerField()
    killmail_hash = models.CharField(max_length=255)
    killmail_time = models.DateTimeField()
    solar_system_id = models.BigIntegerField()
    ship_type_id = models.BigIntegerField()
    victim_character_id = models.BigIntegerField(null=True)
    victim_corporation_id = models.BigIntegerField(null=True)
    victim_alliance_id = models.BigIntegerField(null=True)
    victim_faction_id = models.BigIntegerField(null=True)
    attackers = models.TextField()
    items = models.TextField()
    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["killmail_time"])]


class EveCharacterKillmailAttacker(models.Model):
    killmail = models.ForeignKey(
        "EveCharacterKillmail", on_delete=models.CASCADE, db_index=True
    )
    character_id = models.BigIntegerField(null=True, db_index=True)
    corporation_id = models.BigIntegerField(null=True)
    alliance_id = models.BigIntegerField(null=True)
    faction_id = models.BigIntegerField(null=True)
    ship_type_id = models.BigIntegerField(null=True, db_index=True)


class EveCharacterAsset(models.Model):
    type_id = models.IntegerField(db_index=True)
    type_name = models.CharField(max_length=255)
    location_id = models.BigIntegerField(db_index=True)
    location_name = models.CharField(max_length=255)
    updated = models.DateTimeField(null=True, auto_now=True)
    item_id = models.BigIntegerField(null=True, db_index=True)
    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)


class EveCharacterContract(models.Model):
    """Character contract from ESI (esi-contracts.read_character_contracts.v1)."""

    contract_id = models.BigIntegerField(unique=True, primary_key=True)
    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)
    type = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=32, db_index=True)
    availability = models.CharField(max_length=32, blank=True)
    issuer_id = models.BigIntegerField()
    issuer_corporation_id = models.BigIntegerField(null=True, blank=True)
    assignee_id = models.BigIntegerField(null=True, blank=True)
    acceptor_id = models.BigIntegerField(null=True, blank=True)
    for_corporation = models.BooleanField(default=False)
    date_issued = models.DateTimeField(null=True, blank=True)
    date_expired = models.DateTimeField(null=True, blank=True)
    date_accepted = models.DateTimeField(null=True, blank=True)
    date_completed = models.DateTimeField(null=True, blank=True)
    days_to_complete = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    reward = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    collateral = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    buyout = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    volume = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    start_location_id = models.BigIntegerField(null=True, blank=True)
    end_location_id = models.BigIntegerField(null=True, blank=True)
    title = models.CharField(blank=True, max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["character", "status"])]


class EveCharacterIndustryJob(models.Model):
    """
    Character industry job (manufacturing, research, etc.) from ESI.
    Synced from ESI; job_id is the ESI job identifier.
    """

    job_id = models.BigIntegerField(unique=True, db_index=True)
    character = models.ForeignKey(
        "EveCharacter",
        on_delete=models.CASCADE,
        related_name="industry_jobs",
    )
    activity_id = models.IntegerField(
        help_text="Activity: 1=Manufacturing, 2=Researching TE, 3=Researching ME, etc."
    )
    blueprint_id = models.BigIntegerField()
    blueprint_type_id = models.IntegerField(db_index=True)
    blueprint_location_id = models.BigIntegerField()
    facility_id = models.BigIntegerField()
    location_id = models.BigIntegerField(db_index=True)
    output_location_id = models.BigIntegerField()
    status = models.CharField(max_length=32, db_index=True)
    installer_id = models.BigIntegerField(
        help_text="Character ID that installed the job."
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration = models.PositiveIntegerField(help_text="Duration in seconds.")
    completed_date = models.DateTimeField(null=True, blank=True)
    completed_character_id = models.BigIntegerField(null=True, blank=True)
    runs = models.PositiveIntegerField()
    licensed_runs = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-end_date"]
        indexes = [
            models.Index(fields=["character", "status"]),
        ]

    def __str__(self):
        return f"Job {self.job_id} ({self.character.character_name}, {self.status})"


class EveCharacterBlueprint(models.Model):
    """
    Character blueprint from ESI (esi-characters.read_blueprints.v1).
    item_id is the blueprint instance ID; type_id is the blueprint type.
    """

    item_id = models.BigIntegerField(db_index=True)
    character = models.ForeignKey(
        "EveCharacter",
        on_delete=models.CASCADE,
        related_name="blueprints",
    )
    type_id = models.IntegerField(db_index=True)
    location_id = models.BigIntegerField(db_index=True)
    location_flag = models.CharField(max_length=32, db_index=True)
    material_efficiency = models.SmallIntegerField(
        help_text="ME level 0-10; -1 if not researched."
    )
    time_efficiency = models.SmallIntegerField(
        help_text="TE level 0-20; -1 if not researched."
    )
    quantity = models.IntegerField(
        help_text="Copy count; -1 for BPO (original)."
    )
    runs = models.IntegerField(
        help_text="Manufacturing runs left; -1 for BPO."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("character", "item_id"),)
        indexes = [models.Index(fields=["character", "type_id"])]

    def __str__(self):
        return f"BP {self.item_id} ({self.character.character_name}, type {self.type_id})"


class EveCharacterPlanet(models.Model):
    """A character's planetary interaction colony on a specific planet."""

    character = models.ForeignKey(
        "EveCharacter",
        on_delete=models.CASCADE,
        related_name="planets",
    )
    planet_id = models.IntegerField()
    planet_type = models.CharField(max_length=32)
    solar_system_id = models.IntegerField()
    upgrade_level = models.IntegerField(default=0)
    num_pins = models.IntegerField(default=0)
    last_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the colony was updated in-game (from ESI).",
    )

    class Meta:
        unique_together = ("character", "planet_id")
        indexes = [
            models.Index(fields=["planet_id"]),
            models.Index(fields=["solar_system_id"]),
        ]

    def __str__(self):
        return f"{self.character.character_name} - Planet {self.planet_id} ({self.planet_type})"


class EveCharacterPlanetOutput(models.Model):
    """
    One output of a character's planetary colony.

    Each row represents a resource that a planet either harvests (extractor)
    or produces (factory).  The industry package queries these rows to find
    characters whose planets supply a given type.

    daily_quantity: estimated units produced or harvested per day, from
    extractor cycle_time/qty_per_cycle and factory schematic cycle + route quantity.
    """

    class OutputType(models.TextChoices):
        HARVESTED = "harvested", "Harvested"
        PRODUCED = "produced", "Produced"

    planet = models.ForeignKey(
        EveCharacterPlanet,
        on_delete=models.CASCADE,
        related_name="outputs",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
    )
    output_type = models.CharField(
        max_length=16,
        choices=OutputType.choices,
    )
    daily_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Estimated units produced or harvested per day.",
    )

    class Meta:
        unique_together = ("planet", "eve_type", "output_type")
        indexes = [
            models.Index(fields=["eve_type"]),
            models.Index(fields=["output_type"]),
        ]

    def __str__(self):
        return f"{self.planet} -> {self.eve_type.name} ({self.output_type})"


class EveCharacterMiningEntry(models.Model):
    """
    A single row from a character's personal mining ledger (ESI).

    Each row is one (character, ore-type, day, solar-system) tuple with the
    total units mined.  The industry package queries these rows to find
    characters who mine ores that reprocess into a given mineral.
    """

    character = models.ForeignKey(
        "EveCharacter",
        on_delete=models.CASCADE,
        related_name="mining_entries",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
    )
    date = models.DateField()
    quantity = models.BigIntegerField()
    solar_system_id = models.IntegerField()

    class Meta:
        unique_together = ("character", "eve_type", "date", "solar_system_id")
        indexes = [
            models.Index(fields=["eve_type"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return (
            f"{self.character.character_name} - {self.eve_type.name} "
            f"x{self.quantity} ({self.date})"
        )


class EveCharacterSkillset(models.Model):
    progress = models.FloatField()
    missing_skills = models.TextField(blank=True)
    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)
    eve_skillset = models.ForeignKey("EveSkillset", on_delete=models.CASCADE)


class EveSkillset(models.Model):
    name = models.CharField(max_length=255)
    skills = models.TextField(blank=True)
    total_skill_points = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.name)

    @staticmethod
    def get_skill_name(skill: str):
        return skill[:-1]

    @staticmethod
    def get_skill_level(skill: str):
        return skill[-1]

    def get_number_of_characters_with_skillset(
        self, alliance_name: str = None
    ) -> List[str]:
        character_names = []
        skills = self.skills.split("\n")
        q = Q()
        skill_dict = {}
        for skill in skills:
            skill_name = skill[:-1].strip()
            skill_level = int(skill[-1])
            if (
                skill_name not in skill_dict
                or skill_dict[skill_name] < skill_level
            ):
                skill_dict[skill_name] = skill_level
        for skill_name, skill_level in skill_dict.items():
            q |= Q(skill_name=skill_name, skill_level__gte=skill_level)
        characters = EveCharacter.objects.all()
        if alliance_name:
            alliance_ids = EveAlliance.objects.filter(
                name=alliance_name
            ).values_list("alliance_id", flat=True)
            characters = characters.filter(alliance_id__in=alliance_ids)
        for character in characters:
            if EveCharacterSkill.objects.filter(q).filter(
                character=character
            ).count() == len(skill_dict.keys()):
                character_names.append(character.character_name)
        return character_names

    def get_missing_skills_for_character_id(
        self, character_id: int
    ) -> List[str]:
        character = EveCharacter.objects.get(character_id=character_id)
        skills = self.skills.split("\n")
        missing_skills = []
        for skill in skills:
            skill_name = skill[:-1].strip()
            skill_level = skill[-1].strip()
            if (
                not EveCharacterSkill.objects.filter(
                    skill_name=skill_name, skill_level__gte=skill_level
                )
                .filter(character=character)
                .exists()
            ):
                missing_skills.append(skill)
        return missing_skills

    @staticmethod
    def roman_number_to_int(s):
        roman = {
            "I": 1,
            "V": 5,
            "X": 10,
            "L": 50,
            "C": 100,
            "D": 500,
            "M": 1000,
            "IV": 4,
            "IX": 9,
            "XL": 40,
            "XC": 90,
            "CD": 400,
            "CM": 900,
        }
        i, num = 0, 0
        while i < len(s):
            if i + 1 < len(s) and s[i : i + 2] in roman:
                num += roman[s[i : i + 2]]
                i += 2
            else:
                num += roman[s[i]]
                i += 1
        return num

    def save(self, *args, **kwargs):
        if self.skills:
            parsed_skills = []
            for skill in self.skills.split("\n"):
                skill = skill.strip()
                if not skill:
                    continue
                skill_parts = skill.split(" ")
                skill_name = " ".join(skill_parts[:-1])
                skill_level = skill_parts[-1]
                if skill_level.isnumeric():
                    parsed_skills.append(f"{skill_name} {skill_level}")
                else:
                    parsed_skills.append(
                        f"{skill_name} {self.roman_number_to_int(skill_level)}"
                    )
            self.skills = "\n".join(parsed_skills)
        super().save(*args, **kwargs)
