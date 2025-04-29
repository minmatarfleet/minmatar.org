from django.contrib import admin

from market.models import (
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
    EveMarketItemExpectation,
    EveMarketLocation,
    EveMarketContract,
)

# Register your models here.
admin.site.register(EveMarketLocation)
admin.site.register(EveMarketContractExpectation)
admin.site.register(EveMarketItemExpectation)
admin.site.register(EveMarketContractResponsibility)


@admin.register(EveMarketContract)
class EveMarketContractAdmin(admin.ModelAdmin):
    """
    Custom admin to make working with contracts easier
    """

    list_display = (
        "id",
        "title",
        "status",
        "issuer_external_id",
        "created_at",
    )
    search_fields = ("title", "issuer_external_id")
    list_filter = (
        "status",
        "title",
    )
    date_hierarchy = "created_at"
