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


class EveCorporationContract(models.Model):
    """Corporation contract from ESI (esi-contracts.read_corporation_contracts.v1)."""

    contract_id = models.BigIntegerField(unique=True, primary_key=True)
    corporation = models.ForeignKey(
        EveCorporation, on_delete=models.CASCADE, related_name="contracts"
    )
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
        indexes = [models.Index(fields=["corporation", "status"])]


class EveCorporationIndustryJob(models.Model):
    """
    Corporation industry job (manufacturing, research, etc.) from ESI.
    Synced from ESI; job_id is the ESI job identifier.
    """

    job_id = models.BigIntegerField(unique=True, db_index=True)
    corporation = models.ForeignKey(
        EveCorporation,
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
            models.Index(fields=["corporation", "status"]),
        ]

    def __str__(self):
        return f"Job {self.job_id} ({self.corporation.name}, {self.status})"


class EveCorporationBlueprint(models.Model):
    """
    Corporation blueprint from ESI (esi-corporations.read_blueprints.v1).
    item_id is the blueprint instance ID; type_id is the blueprint type.
    """

    item_id = models.BigIntegerField(db_index=True)
    corporation = models.ForeignKey(
        EveCorporation,
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
        unique_together = (("corporation", "item_id"),)
        indexes = [models.Index(fields=["corporation", "type_id"])]

    def __str__(self):
        return (
            f"BP {self.item_id} ({self.corporation.name}, type {self.type_id})"
        )
