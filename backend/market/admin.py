from django.contrib import admin

from market.models import (
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
    EveMarketItemExpectation,
    EveMarketContract,
    EveMarketContractError,
)


@admin.register(EveMarketContractExpectation)
class EveMarketContractExpectationAdmin(admin.ModelAdmin):
    """Admin for market contract expectations"""

    list_display = (
        "fitting",
        "location",
        "quantity",
        "current_quantity",
        "is_fulfilled",
        "is_understocked",
    )
    search_fields = (
        "fitting__name",
        "fitting__description",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "fitting")
    readonly_fields = (
        "current_quantity",
        "desired_quantity",
        "is_fulfilled",
        "is_understocked",
    )
    autocomplete_fields = ("fitting", "location")
    ordering = ("fitting__name", "location__location_name")
    fieldsets = (
        ("Details", {"fields": ("fitting", "location", "quantity")}),
        (
            "Status",
            {
                "fields": (
                    "current_quantity",
                    "desired_quantity",
                    "is_fulfilled",
                    "is_understocked",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(EveMarketItemExpectation)
class EveMarketItemExpectationAdmin(admin.ModelAdmin):
    """Admin for market item expectations"""

    list_display = ("item", "location", "quantity")
    search_fields = (
        "item__name",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "item")
    autocomplete_fields = ("location",)


@admin.register(EveMarketContractResponsibility)
class EveMarketContractResponsibilityAdmin(admin.ModelAdmin):
    """Admin for market contract responsibilities"""

    list_display = ("expectation", "entity_id", "get_fitting", "get_location")
    search_fields = (
        "entity_id",
        "expectation__fitting__name",
        "expectation__location__location_name",
    )
    list_filter = ("expectation__location", "expectation__fitting")
    autocomplete_fields = ("expectation",)

    def get_fitting(self, obj):
        return obj.expectation.fitting.name

    get_fitting.short_description = "Fitting"

    def get_location(self, obj):
        return obj.expectation.location.location_name

    get_location.short_description = "Location"


@admin.register(EveMarketContractError)
class EveMarketContractErrorAdmin(admin.ModelAdmin):
    """Admin for market contract errors"""

    list_display = ("title", "issuer", "location", "quantity", "updated_at")
    search_fields = (
        "title",
        "issuer__character_name",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "updated_at")
    readonly_fields = ("updated_at",)
    date_hierarchy = "updated_at"
    autocomplete_fields = ("issuer", "location")


@admin.register(EveMarketContract)
class EveMarketContractAdmin(admin.ModelAdmin):
    """Custom admin to make working with contracts easier"""

    list_display = (
        "id",
        "title",
        "status",
        "fitting",
        "location",
        "issuer_external_id",
        "price",
        "created_at",
    )
    search_fields = (
        "title",
        "id",
        "issuer_external_id",
        "fitting__name",
        "location__location_name",
    )
    list_filter = (
        "status",
        "is_public",
        "location",
        "fitting",
        "created_at",
    )
    readonly_fields = (
        "created_at",
        "completed_at",
        "last_updated",
        "issued_at",
        "expires_at",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ("location", "fitting")
    fieldsets = (
        (
            "Contract Details",
            {"fields": ("id", "title", "status", "price", "is_public")},
        ),
        (
            "Parties",
            {"fields": ("issuer_external_id", "assignee_id", "acceptor_id")},
        ),
        ("Relationships", {"fields": ("location", "fitting")}),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "issued_at",
                    "expires_at",
                    "completed_at",
                    "last_updated",
                ),
                "classes": ("collapse",),
            },
        ),
    )
