import logging

from django.db import models
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveFaction

from eveonline.scopes import CEO_SCOPES

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


class EvePrimaryCharacter(models.Model):
    """Primary character model"""

    character = models.ForeignKey("EveCharacter", on_delete=models.CASCADE)


class EveCharacter(models.Model):
    """Character model"""

    character_id = models.IntegerField(unique=True)
    character_name = models.CharField(max_length=255, blank=True)
    corporation = models.ForeignKey(
        "EveCorporation", on_delete=models.CASCADE, blank=True, null=True
    )

    token = models.OneToOneField(Token, on_delete=models.CASCADE, null=True)

    # data
    skills_json = models.TextField(blank=True, default="{}")
    assets_json = models.TextField(blank=True, default="{}")

    @property
    def tokens(self):
        return Token.objects.filter(character_id=self.character_id)

    def __str__(self):
        return str(self.character_name)


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
        if self.alliance and self.alliance.id == 99011978:
            return "alliance"
        elif self.alliance and self.alliance.id == 99012009:
            return "associate"
        elif self.faction and self.faction.id == 500002:
            return "militia"
        else:
            return "public"

    @property
    def active(self):
        if not self.ceo:
            return False
        if Token.objects.filter(
            character_id=self.ceo.character_id,
            scopes__name="esi-contracts.read_corporation_contracts.v1",
        ).exists():
            # check if has required scopes
            ceo_token = Token.objects.get(
                character_id=self.ceo.character_id,
                scopes__name="esi-contracts.read_corporation_contracts.v1",
            )
            token_scopes = set(
                [scope.name for scope in ceo_token.scopes.all()]
            )
            required_scopes = set(CEO_SCOPES)
            if token_scopes.issuperset(required_scopes):
                return True
        return False

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
