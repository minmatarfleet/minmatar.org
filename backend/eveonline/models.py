import logging
from typing import List

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from esi.models import Token
from eveuniverse.models import EveFaction

from eveonline.client import EsiClient

logger = logging.getLogger(__name__)


class EvePlayer(models.Model):
    """Represents an Eve Online player"""

    # Website nickname is same as username by default, but can be changed.
    nickname = models.CharField(max_length=255, unique=True)

    primary_character = models.OneToOneField(
        "EveCharacter",
        on_delete=models.SET_NULL,
        null=True,
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
        max_length=16,
        choices=prime_choices,
        null=True,
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
    corporation = models.ForeignKey(
        "EveCorporation", on_delete=models.SET_NULL, blank=True, null=True
    )
    alliance = models.ForeignKey(
        "EveAlliance", on_delete=models.SET_NULL, blank=True, null=True
    )
    faction = models.ForeignKey(
        EveFaction, on_delete=models.SET_NULL, blank=True, null=True
    )

    token = models.ForeignKey(
        Token, on_delete=models.SET_NULL, null=True, blank=True
    )
    exempt = models.BooleanField(default=False)

    # True if ESI API calls should not be made for this character
    esi_suspended = models.BooleanField(default=False)

    # The level of access to Eve Swagger Interface APIs granted by this character
    esi_token_level = models.CharField(max_length=40, null=True, blank=True)

    # The my.minmatar.org user that owns this Eve character
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.character_name)

    def summary(self):
        return f"{self.character_name} ({self.character_id})"

    @property
    def is_primary(self) -> bool:
        """Check if this character is the primary character via EvePlayer"""
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
    """A tag that can be applied to an EveCharacter"""

    title = models.CharField(max_length=40, default="TBC")
    description = models.CharField(max_length=255)
    image_name = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterTag(models.Model):
    """The tags applied to a specific EveCharacter"""

    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    tag = models.ForeignKey(EveTag, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (("character", "tag"),)


class EveCharacterLog(models.Model):
    """Character log model"""

    username = models.CharField(max_length=255)
    character_name = models.CharField(max_length=255)
    added = models.DateTimeField(auto_now_add=True, null=True)

    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterSkill(models.Model):
    """Character skill model"""

    skill_id = models.IntegerField()
    skill_name = models.CharField(max_length=255)
    skill_points = models.IntegerField()
    skill_level = models.IntegerField()

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class EveCharacterKillmail(models.Model):
    """Killmail model"""

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
        indexes = [
            models.Index(fields=["killmail_time"]),
        ]


class EveCharacterKillmailAttacker(models.Model):
    """Killmail attacker model"""

    killmail = models.ForeignKey(
        "EveCharacterKillmail", on_delete=models.CASCADE, db_index=True
    )
    character_id = models.BigIntegerField(null=True, db_index=True)
    corporation_id = models.BigIntegerField(null=True)
    alliance_id = models.BigIntegerField(null=True)
    faction_id = models.BigIntegerField(null=True)
    ship_type_id = models.BigIntegerField(null=True, db_index=True)


class EveCharacterAsset(models.Model):
    """Character asset model"""

    type_id = models.IntegerField(db_index=True)
    type_name = models.CharField(max_length=255)
    location_id = models.BigIntegerField(db_index=True)
    location_name = models.CharField(max_length=255)
    updated = models.DateTimeField(null=True, auto_now=True)
    item_id = models.BigIntegerField(null=True, db_index=True)

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)


class EveCharacterSkillset(models.Model):
    """List of skills to compare character skills against for progression"""

    progress = models.FloatField()
    missing_skills = models.TextField(blank=True)

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)
    eve_skillset = models.ForeignKey("EveSkillset", on_delete=models.CASCADE)


class EveSkillset(models.Model):
    """List of skills to compare character skills against for progression"""

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
        skillset = self
        skills = skillset.skills.split("\n")
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
            characters = characters.filter(alliance__name=alliance_name)
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
        skillset = self
        skills = skillset.skills.split("\n")

        missing_skills = []
        for skill in skills:
            # Skill name is everything except the last character
            skill_name = skill[:-1].strip()
            # Skill level is the last character
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
        """
        :type s: str
        :rtype: int
        """
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
        i = 0
        num = 0
        while i < len(s):
            if i + 1 < len(s) and s[i : i + 2] in roman:
                num += roman[s[i : i + 2]]
                i += 2
            else:
                # print(i)
                num += roman[s[i]]
                i += 1
        return num

    # parse skills and get last element, convert to int if necessary
    # skill line example: "My Skill V"
    # use roman_number_to_int
    def save(self, *args, **kwargs):
        if self.skills:
            logger.debug("Parsing skills for %s", self.name)
            parsed_skills = []
            skills = self.skills.split("\n")
            for skill in skills:
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


class EveCorporation(models.Model):
    """Corporation model"""

    corporation_id = models.IntegerField(unique=True)
    introduction = models.TextField(blank=True)
    biography = models.TextField(blank=True)
    timezones = models.TextField(blank=True)
    requirements = models.TextField(blank=True)

    # autopopulated
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True, null=True)
    member_count = models.IntegerField(blank=True, null=True)

    recruitment_active = models.BooleanField(default=True)

    # relationships
    ceo = models.ForeignKey(
        "EveCharacter", on_delete=models.SET_NULL, blank=True, null=True
    )
    alliance = models.ForeignKey(
        "EveAlliance", on_delete=models.SET_NULL, blank=True, null=True
    )
    faction = models.ForeignKey(
        EveFaction, on_delete=models.SET_NULL, blank=True, null=True
    )

    # Role-based character sets (populated from ESI corporation roles)
    directors = models.ManyToManyField(
        "EveCharacter",
        related_name="corporation_director_of",
        blank=True,
    )
    recruiters = models.ManyToManyField(
        "EveCharacter",
        related_name="corporation_recruiter_of",
        blank=True,
    )
    stewards = models.ManyToManyField(
        "EveCharacter",
        related_name="corporation_steward_of",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @property
    def type(self):
        if self.alliance and self.alliance.alliance_id == 99011978:
            return "alliance"
        elif self.alliance and self.alliance.alliance_id == 99012009:
            return "associate"
        elif self.faction and self.faction.id == 500002:
            return "militia"
        else:
            return "public"

    @property
    def active(self):
        return self.recruitment_active
        # if not self.ceo:
        #     return False

        # if not self.ceo.token:
        #     return False

        # if not Token.get_token(
        #     self.ceo.character_id,
        #     ["esi-corporations.read_corporation_membership.v1"],
        # ):
        #     logger.debug(
        #         "CEO token does not have required scope: %s", self.name
        #     )
        #     return False

        # return True

    def populate(self):
        logger.info(
            "Fetching external corporation details for %s", self.corporation_id
        )
        esi_corporation = (
            EsiClient(None).get_corporation(self.corporation_id).results()
        )
        logger.debug("ESI corporation data: %s", esi_corporation)
        self.name = esi_corporation["name"]
        self.ticker = esi_corporation["ticker"]
        self.member_count = esi_corporation["member_count"]

        esi_alliance_id = esi_corporation["alliance_id"]
        if esi_alliance_id:
            self.alliance, _ = EveAlliance.objects.get_or_create(
                # Details will be pulled from ESI via post_save signal
                alliance_id=esi_alliance_id
            )
        else:
            self.alliance = None

        # set ceo
        if esi_corporation["ceo_id"] > 90000000:
            logger.info(
                "Setting CEO as %s for corporation %s",
                esi_corporation["ceo_id"],
                self.name,
            )
            self.ceo = EveCharacter.objects.get_or_create(
                character_id=esi_corporation["ceo_id"]
            )[0]
        elif esi_corporation["ceo_id"] == 1:
            if self.id is not None:
                logger.info("Deleting corporation %s", self.name)
                self.delete()
                return
        else:
            logger.info("Skipping CEO for corporation %s", self.name)
        # affiliations are set by update_character_affilliations
        # better endpoint / faster
        self.save()

    def __str__(self):
        return str(self.name)


class EveAlliance(models.Model):
    """Alliance model"""

    alliance_id = models.IntegerField(unique=True)

    # autopopulated
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return str(self.name)


class EveLocation(models.Model):
    """An alliance location for freight, market or staging"""

    location_id = models.BigIntegerField(primary_key=True)
    location_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32)
    region_id = models.BigIntegerField(null=True)

    market_active = models.BooleanField(default=False)
    freight_active = models.BooleanField(default=False)
    staging_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(f"{self.location_name}")
