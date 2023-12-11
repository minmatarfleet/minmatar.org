from django.db import models
from django.contrib.auth.models import User
from esi.models import Token
from esi.clients import EsiClientProvider

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
        "esi-corporations.read_corporation_roles.v1",
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
    alliance_id = models.IntegerField(blank=True)
    faction_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    def active(self):
        if Token.objects.filter(character_id=self.ceo_id).exists():
            # check if has required scopes
            ceo_token = Token.objects.get(character_id=self.ceo_id)
            if set(self.required_ceo_scopes).issubset(
                set(ceo_token.scopes.all())
            ):
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
