import logging

from django.db import models
from eveuniverse.models import EveFaction

from eveonline.client import EsiClient
from eveonline.models.alliances import EveAlliance
from eveonline.models.characters import EveCharacter

logger = logging.getLogger(__name__)


class EveCorporation(models.Model):
    """Corporation model"""

    corporation_id = models.IntegerField(unique=True)
    introduction = models.TextField(blank=True)
    biography = models.TextField(blank=True)
    timezones = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True, null=True)
    member_count = models.IntegerField(blank=True, null=True)
    recruitment_active = models.BooleanField(default=True)
    generate_corporation_groups = models.BooleanField(
        default=False,
        help_text="When enabled, create and sync Corp <TICKER>, Recruiter, Director, and Gunner groups.",
    )
    ceo = models.ForeignKey(
        EveCharacter, on_delete=models.SET_NULL, blank=True, null=True
    )
    alliance = models.ForeignKey(
        EveAlliance, on_delete=models.SET_NULL, blank=True, null=True
    )
    faction = models.ForeignKey(
        EveFaction, on_delete=models.SET_NULL, blank=True, null=True
    )
    directors = models.ManyToManyField(
        EveCharacter, related_name="corporation_director_of", blank=True
    )
    recruiters = models.ManyToManyField(
        EveCharacter, related_name="corporation_recruiter_of", blank=True
    )
    stewards = models.ManyToManyField(
        EveCharacter, related_name="corporation_steward_of", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @property
    def type(self):
        if self.alliance and self.alliance.alliance_id == 99011978:
            return "alliance"
        if self.alliance and self.alliance.alliance_id == 99012009:
            return "associate"
        if self.faction and self.faction.id == 500002:
            return "militia"
        return "public"

    @property
    def active(self):
        return self.recruitment_active

    def populate(self):
        logger.info(
            "Fetching external corporation details for %s", self.corporation_id
        )
        esi_corporation = (
            EsiClient(None).get_corporation(self.corporation_id).results()
        )
        self.name = esi_corporation["name"]
        self.ticker = esi_corporation["ticker"]
        self.member_count = esi_corporation["member_count"]
        esi_alliance_id = esi_corporation["alliance_id"]
        if esi_alliance_id:
            self.alliance = EveAlliance.objects.filter(
                alliance_id=esi_alliance_id
            ).first()
        else:
            self.alliance = None
        if esi_corporation["ceo_id"] > 90000000:
            self.ceo = EveCharacter.objects.get_or_create(
                character_id=esi_corporation["ceo_id"]
            )[0]
        elif esi_corporation["ceo_id"] == 1 and self.id is not None:
            self.delete()
            return
        self.save()

    def __str__(self):
        return str(self.name)
