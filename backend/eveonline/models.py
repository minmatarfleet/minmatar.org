import logging

from django.db import models
from esi.clients import EsiClientProvider
from esi.models import Scope, Token
from eveuniverse.models import EveFaction

from eveonline.scopes import CEO_SCOPES
from django.db.models import Q
from typing import List

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


class EvePrimaryCharacter(models.Model):
    """Primary character model"""

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)

    def __str__(self):
        return str(self.character.character_name)


class EvePrimaryCharacterChangeLog(models.Model):
    """Primary character change log model"""

    username = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    previous_character_name = models.CharField(max_length=255)
    new_character_name = models.CharField(max_length=255)


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

    token = models.OneToOneField(
        Token, on_delete=models.CASCADE, null=True, blank=True
    )
    exempt = models.BooleanField(default=False)

    # data
    skills_json = models.TextField(blank=True, default="{}")
    assets_json = models.TextField(blank=True, default="{}")

    @property
    def tokens(self):
        return Token.objects.filter(character_id=self.character_id)

    def __str__(self):
        return str(self.character_name)

    class Meta:
        indexes = [
            models.Index(fields=["character_name"]),
        ]


class EveCharacterLog(models.Model):
    """Character log model"""

    username = models.CharField(max_length=255)
    character_name = models.CharField(max_length=255)


class EveCharacterSkill(models.Model):
    """Character skill model"""

    skill_id = models.IntegerField()
    skill_name = models.CharField(max_length=255)
    skill_points = models.IntegerField()
    skill_level = models.IntegerField()

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)


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


class EveCharacterKillmailAttacker(models.Model):
    """Killmail attacker model"""

    killmail = models.ForeignKey(
        "EveCharacterKillmail", on_delete=models.CASCADE
    )
    character_id = models.BigIntegerField(null=True)
    corporation_id = models.BigIntegerField(null=True)
    alliance_id = models.BigIntegerField(null=True)
    faction_id = models.BigIntegerField(null=True)
    ship_type_id = models.BigIntegerField(null=True)


class EveCharacterAsset(models.Model):
    """Character asset model"""

    type_id = models.IntegerField()
    type_name = models.CharField(max_length=255)
    location_id = models.BigIntegerField()
    location_name = models.CharField(max_length=255)

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

    def __str__(self):
        return str(self.name)

    @staticmethod
    def get_skill_name(skill: str):
        return skill[:-1]

    @staticmethod
    def get_skill_level(skill: str):
        return skill[-1]

    def get_number_of_characters_with_skillset(self) -> List[str]:
        character_names = []
        skillset = self
        skills = skillset.skills.split("\n")
        q = Q()
        for skill in skills:
            # Skill name is everything except the last character
            skill_name = skill[:-1]
            # Skill level is the last character
            skill_level = skill[-1]
            q |= Q(skill_name=skill_name, skill_level__lt=skill_level)

        for character in EveCharacter.objects.all():
            if (
                EveCharacterSkill.objects.filter(q)
                .filter(character=character)
                .exists()
            ):
                continue

            if (
                EveCharacterSkill.objects.filter(character=character).count()
                == 0
            ):
                continue
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
            logger.info("Parsing skills for %s", self.name)
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
        if not self.ceo:
            return False

        if not self.ceo.token:
            return False

        # Grab CEO token for the character
        token = Token.objects.filter(
            character_id=self.ceo.character_id,
            scopes__name="esi-corporations.read_corporation_membership.v1",
        ).first()
        if not token:
            return False

        # Check if the token has the required scopes
        required_scopes = set(CEO_SCOPES)
        required_scopes = Scope.objects.filter(
            name__in=required_scopes,
        )

        for scope in required_scopes:
            if scope not in token.scopes.all():
                return False

        return True

    def populate(self):
        logger.info(
            "Fetching external corporation details for %s", self.corporation_id
        )
        esi_corporation = (
            esi.client.Corporation.get_corporations_corporation_id(
                corporation_id=self.corporation_id
            ).results()
        )
        logger.info("ESI corporation data: %s", esi_corporation)
        self.name = esi_corporation["name"]
        self.ticker = esi_corporation["ticker"]
        self.member_count = esi_corporation["member_count"]
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

        # set alliance
        logger.info("Updating alliance for corporation %s", self.name)
        if (
            "alliance_id" in esi_corporation
            and esi_corporation["alliance_id"] is not None
        ):
            logger.info("Setting alliance for corporation %s", self.name)
            alliance = EveAlliance.objects.get_or_create(
                alliance_id=esi_corporation["alliance_id"]
            )[0]
            logger.info(
                "Alliance for corporation %s is %s", self.name, alliance
            )
            self.alliance = alliance
        else:
            self.alliance = None
            logger.info("Corporation %s has no alliance", self.name)
        # set faction
        logger.info("Updating faction for corporation %s", self.name)
        if (
            "faction_id" in esi_corporation
            and esi_corporation["faction_id"] is not None
        ):
            logger.info("Setting faction for corporation %s", self.name)
            self.faction = EveFaction.objects.get_or_create_esi(
                id=esi_corporation["faction_id"]
            )[0]
        else:
            self.faction = None
            logger.info("Corporation %s has no faction", self.name)
        self.save()

    def __str__(self):
        return str(self.name)


class EveAlliance(models.Model):
    """Alliance model"""

    alliance_id = models.IntegerField()

    # autopopulated
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return str(self.name)
