from django.db import models
from django.contrib.auth.models import User
from esi.models import Token
from esi.clients import EsiClientProvider
import logging
import json

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


# Create your models here.
class EvePrimaryToken(models.Model):
    """Allow users to set a primary token, essentially their main character"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="eve_primary_token"
    )
    token = models.OneToOneField(Token, on_delete=models.CASCADE)


class EveCorporation(models.Model):
    """Corporation model"""

    required_ceo_scopes = [
        "esi-corporations.read_corporation_membership.v1",
        "esi-corporations.read_structures.v1",
        "esi-corporations.read_blueprints.v1",
        "esi-corporations.read_contacts.v1",
        "esi-corporations.read_container_logs.v1",
        "esi-corporations.read_divisions.v1",
        "esi-corporations.read_facilities.v1",
        "esi-corporations.read_fw_stats.v1",
        "esi-corporations.read_medals.v1",
        "esi-corporations.read_starbases.v1",
        "esi-corporations.read_titles.v1",
        "esi-wallet.read_corporation_wallets.v1",
        "esi-contracts.read_corporation_contracts.v1",
    ]

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
            required_scopes = set(self.required_ceo_scopes)
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
        super(EveCorporation, self).save(*args, **kwargs)


class EveCharacter(models.Model):
    """Character model"""

    character_id = models.IntegerField()
    character_name = models.CharField(max_length=255, blank=True)
    corporation = models.ForeignKey(
        EveCorporation, on_delete=models.CASCADE, blank=True, null=True
    )

    # data
    skills_json = models.TextField(blank=True)

    @property
    def tokens(self):
        return Token.objects.filter(character_id=self.character_id)

    def __str__(self):
        return self.character_name

    def save(self, *args, **kwargs):
        esi_character = esi.client.Character.get_characters_character_id(
            character_id=self.character_id
        ).results()
        logger.debug("Setting character name to %s", esi_character["name"])
        self.character_name = esi_character["name"]
        logger.debug(
            "Setting corporation to %s", esi_character["corporation_id"]
        )
        if EveCorporation.objects.filter(
            corporation_id=esi_character["corporation_id"]
        ).exists():
            self.corporation = EveCorporation.objects.get(
                corporation_id=esi_character["corporation_id"]
            )
        else:
            corporation = EveCorporation.objects.create(
                corporation_id=esi_character["corporation_id"]
            )
            self.corporation = corporation

        # fetch skills
        if self.tokens.exists():
            logger.debug("Fetching skills for %s", self.character_name)
            required_scopes = ["esi-skills.read_skills.v1"]
            token = Token.objects.filter(
                character_id=self.character_id,
                scopes__name__in=required_scopes,
            ).first()
            if token:
                response = (
                    esi.client.Skills.get_characters_character_id_skills(
                        character_id=self.character_id,
                        token=token.valid_access_token(),
                    ).results()
                )
                self.skills_json = json.dumps(response)

        super(EveCharacter, self).save(*args, **kwargs)


class EveCharacterSkillset(models.Model):
    """List of skills to compare character skills against for progression"""

    name = models.CharField(max_length=255)
    skills = models.TextField(blank=True)
    total_skill_points = models.BigIntegerField()

    def __str__(self):
        return str(self.name)


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
