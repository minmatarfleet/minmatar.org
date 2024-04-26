import logging

from django.db import models
from esi.clients import EsiClientProvider
from esi.models import Scope, Token
from eveuniverse.models import EveFaction

from eveonline.scopes import CEO_SCOPES

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


class EvePrimaryCharacter(models.Model):
    """Primary character model"""

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)

    def __str__(self):
        return str(self.character.character_name)


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


class EveCorporation(models.Model):
    """Corporation model"""

    corporation_id = models.IntegerField()

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
