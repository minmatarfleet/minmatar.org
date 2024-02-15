import logging

from django.contrib.auth.models import User
from django.db import models
from esi.clients import EsiClientProvider
from esi.models import Token

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

    @property
    def tokens(self):
        return Token.objects.filter(character_id=self.character_id)

    def __str__(self):
        return str(self.character_name)


class EveCharacterSkillset(models.Model):
    """List of skills to compare character skills against for progression"""

    name = models.CharField(max_length=255)
    skills = models.TextField(blank=True)
    total_skill_points = models.BigIntegerField()

    def __str__(self):
        return str(self.name)


class EveCorporation(models.Model):
    """Corporation model"""

    types = (
        ("alliance", "Alliance"),
        ("militia", "Militia"),
        ("associate", "Associate"),
        ("public", "Public"),
    )

    corporation_id = models.IntegerField()

    # autopopulated
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=10, choices=types, blank=True)
    member_count = models.IntegerField(blank=True)
    ceo_id = models.IntegerField(blank=True)
    alliance_id = models.IntegerField(blank=True, null=True)
    faction_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    def active(self):
        if Token.objects.filter(
            character_id=self.ceo_id,
            scopes__name="esi-contracts.read_corporation_contracts.v1",
        ).exists():
            # check if has required scopes
            ceo_token = Token.objects.get(
                character_id=self.ceo_id,
                scopes__name="esi-contracts.read_corporation_contracts.v1",
            )
            token_scopes = set(
                [scope.name for scope in ceo_token.scopes.all()]
            )
            required_scopes = set(CEO_SCOPES)
            if token_scopes.issuperset(required_scopes):
                return True
        return False

    def save(self, *args, **kwargs):
        esi_corporation = (
            esi.client.Corporation.get_corporations_corporation_id(
                corporation_id=self.corporation_id
            ).results()
        )
        self.name = esi_corporation["name"]
        self.ceo_id = esi_corporation["ceo_id"]
        self.ticker = esi_corporation["ticker"]
        self.member_count = esi_corporation["member_count"]
        self.alliance_id = esi_corporation["alliance_id"]
        self.faction_id = esi_corporation["faction_id"]
        if self.alliance_id == 99011978:
            self.type = "alliance"
        elif self.alliance_id == 99012009:
            self.type = "associate"
        elif self.faction_id == 500002:
            self.type = "militia"
        else:
            self.type = "public"
        super().save(*args, **kwargs)


class EveCorporationApplication(models.Model):
    """Corporation application model"""

    status_choices = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    )
    status = models.CharField(
        max_length=10, choices=status_choices, default="pending"
    )
    description = models.TextField(blank=True)
    corporation = models.ForeignKey(EveCorporation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    discord_thread_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self):
        return self.user.eve_primary_token.token.character_name


class EveAlliance(models.Model):
    """Alliance model"""

    alliance_id = models.IntegerField()

    # autopopulated
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)
    executor_corporation_id = models.IntegerField(blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        esi_alliance = esi.client.Alliance.get_alliances_alliance_id(
            alliance_id=self.alliance_id
        ).results()
        self.name = esi_alliance["name"]
        self.ticker = esi_alliance["ticker"]
        self.executor_corporation_id = esi_alliance["executor_corporation_id"]
        super().save(*args, **kwargs)
