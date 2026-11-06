# pylint: disable=protected-access
"""House standards for the Django admin (issue #3014).

The admin is the break-glass tool for superusers and the Technology team, so
every registered model gets the same basics: list columns, search, filters,
bounded foreign key widgets, and view-only access for logs and rollups.
``apply_admin_standards`` runs once after ``admin.autodiscover`` (see
``app.admin_config``) and fills in whatever an admin did not choose itself, so
a new admin inherits the standard.  ``app.tests.test_admin_standards`` fails
when a model slips through.
"""

from django.contrib import admin
from django.db import models


def _labels(*labels):
    return frozenset(label.lower() for label in labels)


# Append-only logs, ledgers, Celery-rebuilt rollups, ESI mirrors and raw market
# data.  Wrong data is fixed by re-syncing, not by a hand edit.
READ_ONLY_MODELS = _labels(
    # Audit and history
    "audit.AuditEntry",
    "fittings.EveFittingHistory",
    "fittings.EveDoctrineHistory",
    "tribes.TribeGroupMembershipHistory",
    "tribes.TribeGroupMembershipCharacterHistory",
    "groups.UserCommunityStatusHistory",
    "surveys.SurveyChangelogEntry",
    # Ledgers (the LP ledger stays editable: staff post manual credits)
    "buyback.BuybackLedgerEntry",
    "industry.IndustryLoyaltyPointPriceHistory",
    # Rollups and snapshots
    "alliance.AllianceHealthSnapshot",
    "buyback.BuybackHangarSnapshot",
    "campaigns.CampaignSystemSnapshot",
    "campaigns.CampaignAdvantageReading",
    "campaigns.CampaignAdvantageState",
    "campaigns.CampaignParticipantDay",
    "campaigns.CampaignParticipantStat",
    "campaigns.CampaignKillmail",
    "campaigns.CampaignKillmailParticipant",
    "campaigns.CampaignSiteCompletion",
    "campaigns.CampaignComplexCompletion",
    "campaigns.CampaignEvent",
    "surveys.SurveyQuestionAggregate",
    "capabilities.SdeSnapshot",
    "capabilities.FittingRequirementSet",
    "capabilities.CharacterFittingReadiness",
    "capabilities.CharacterCapability",
    # ESI mirrors
    "eveonline.EveCharacterAsset",
    "eveonline.EveCharacterSkill",
    "eveonline.EveCharacterContract",
    "eveonline.EveCharacterIndustryJob",
    "eveonline.EveCharacterBlueprint",
    "eveonline.EveCharacterClone",
    "eveonline.EveCharacterPlanet",
    "eveonline.EveCharacterFwLpPayout",
    "eveonline.EveCorporationContract",
    "eveonline.EveCorporationIndustryJob",
    "eveonline.EveCorporationWalletJournalEntry",
    "eveonline.EveCorporationProject",
    "eveonline.EveCorporationBlueprint",
    # Raw market data
    "market.EveMarketItemOrder",
    "market.EveMarketItemTransaction",
    "market.EveMarketItemHistory",
    "market.EveMarketInferredSale",
    "market.EveMarketContract",
    "market.EveMarketContractError",
    "market.EveMarketOrderBookSync",
    "market.FittingBuyJitaCheck",
    # Misc logs
    "referrals.ReferralClick",
    "notifications.NotificationDelivery",
)

# Tables that run to millions of rows in production: no COUNT(*) on the list.
LARGE_TABLES = _labels(
    "market.EveMarketItemOrder",
    "market.EveMarketItemTransaction",
    "market.EveMarketItemHistory",
    "market.EveMarketInferredSale",
    "eveonline.EveCharacterAsset",
    "eveonline.EveCharacterSkill",
    "eveonline.EveCharacterBlueprint",
    "eveonline.EveCorporationWalletJournalEntry",
    "campaigns.CampaignKillmailParticipant",
    "campaigns.CampaignKillmail",
    "notifications.NotificationDelivery",
    "audit.AuditEntry",
)

# Foreign keys to these models must not render as a <select> over every row.
LARGE_FK_TARGETS = _labels(
    "auth.User",
    "eveonline.EveCharacter",
    "eveonline.EvePlayer",
    "eveonline.EveCorporation",
    "fittings.EveFitting",
    "fittings.EveDoctrine",
    "campaigns.Campaign",
    "fleets.EveFleet",
    "industry.IndustryOrder",
    "discord.DiscordUser",
    "posts.EvePost",
    "eveuniverse.EveType",
    "eveuniverse.EveGroup",
    "eveuniverse.EvePlanet",
    "eveuniverse.EveMoon",
    "eveuniverse.EveSolarSystem",
    "eveuniverse.EveConstellation",
    "eveuniverse.EveRegion",
)

# Internals hidden from staff who are not superusers.
SUPERUSER_ONLY_APPS = frozenset({"eveuniverse", "django_celery_beat"})

SEARCH_NAME_FIELDS = ("name", "title", "username", "slug", "ticker", "code")
SKIP_LIST_FIELD_TYPES = (
    models.TextField,
    models.JSONField,
    models.BinaryField,
)


class ReadOnlyAdminMixin:
    """View-only admin: no add, change or delete."""

    def has_add_permission(self, request, *args, **kwargs):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SuperuserOnlyAdminMixin:
    """Hide the model (and its app block) from non-superusers.

    ``has_view_or_change_permission`` is view OR change, so denying view alone
    still lets a staff user with the model permission open the change form.
    """

    def has_module_permission(self, request):
        return request.user.is_superuser and super().has_module_permission(
            request
        )

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_view_permission(
            request, obj
        )

    def has_add_permission(self, request, *args, **kwargs):
        return request.user.is_superuser and super().has_add_permission(
            request, *args, **kwargs
        )

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(
            request, obj
        )


def model_key(model):
    return model._meta.label_lower


def _concrete_fields(model):
    return [f for f in model._meta.concrete_fields if not f.primary_key]


def default_list_display(model):
    """`__str__` plus up to four short scalar columns."""
    columns = []
    for field in _concrete_fields(model):
        if isinstance(field, SKIP_LIST_FIELD_TYPES):
            continue
        if field.name == "password":
            continue
        columns.append(field.name)
        if len(columns) == 4:
            break
    return ("__str__", *columns)


def default_search_fields(model):
    """Name-like text columns, else the user/character FK, else the id."""
    fields = []
    concrete = {f.name: f for f in model._meta.concrete_fields}
    for name in SEARCH_NAME_FIELDS:
        field = concrete.get(name)
        if isinstance(field, (models.CharField, models.SlugField)):
            fields.append(name)
    if not fields:
        for field in _concrete_fields(model):
            if (
                isinstance(field, models.CharField)
                and not field.choices
                and len(fields) < 2
            ):
                fields.append(field.name)
    relation = concrete.get("user")
    if relation is not None and relation.is_relation:
        fields.append("user__username")
    relation = concrete.get("character")
    if relation is not None and relation.is_relation:
        fields.append("character__character_name")
    return tuple(fields) or ("id",)


def default_list_filter(model):
    filters = []
    for field in _concrete_fields(model):
        if isinstance(field, models.BooleanField) or (
            field.choices and not field.is_relation
        ):
            filters.append(field.name)
        if len(filters) == 3:
            break
    for field in _concrete_fields(model):
        if isinstance(field, models.DateTimeField):
            filters.append(field.name)
            break
    return tuple(filters)


def unbounded_fk_fields(opts):
    """Editable FK/M2M fields to large models that render as full selects."""
    bounded = (
        set(opts.raw_id_fields or ())
        | set(opts.autocomplete_fields or ())
        | set(opts.readonly_fields or ())
        | set(opts.exclude or ())
        | set(opts.filter_horizontal or ())
        | set(opts.filter_vertical or ())
    )
    found = []
    model = opts.model
    for field in list(model._meta.concrete_fields) + list(
        model._meta.many_to_many
    ):
        if not field.is_relation or not field.editable:
            continue
        if field.name in bounded or field.auto_created:
            continue
        target = field.related_model
        if target is None or model_key(target) not in LARGE_FK_TARGETS:
            continue
        found.append(field.name)
    return found


def _bound_relations(opts):
    """Switch large FK widgets to raw id inputs (in place)."""
    extra = unbounded_fk_fields(opts)
    if extra:
        opts.raw_id_fields = tuple(
            dict.fromkeys((*(opts.raw_id_fields or ()), *extra))
        )


def _mix_in(model_admin, mixin):
    if not isinstance(model_admin, mixin):
        model_admin.__class__ = type(
            model_admin.__class__.__name__,
            (mixin, model_admin.__class__),
            {},
        )


def _standardise(model, model_admin):
    key = model_key(model)

    if key in READ_ONLY_MODELS:
        _mix_in(model_admin, ReadOnlyAdminMixin)
    if model._meta.app_label in SUPERUSER_ONLY_APPS:
        _mix_in(model_admin, SuperuserOnlyAdminMixin)

    if tuple(model_admin.list_display) == ("__str__",):
        model_admin.list_display = default_list_display(model)
    if not model_admin.search_fields:
        model_admin.search_fields = default_search_fields(model)
    if not model_admin.list_filter and not model_admin.date_hierarchy:
        model_admin.list_filter = default_list_filter(model)

    if key in LARGE_TABLES:
        model_admin.show_full_result_count = False
        if not model_admin.list_select_related:
            model_admin.list_select_related = True

    _bound_relations(model_admin)
    for inline_class in model_admin.inlines or ():
        _bound_relations(inline_class)


def apply_admin_standards(site=None):
    """Idempotent: fill in the house defaults on every registered admin."""
    site = site or admin.site
    for model, model_admin in list(
        site._registry.items()
    ):  # pylint: disable=protected-access
        _standardise(model, model_admin)
