from django.contrib import admin

from market.models import (
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
    EveMarketItemExpectation,
    EveMarketLocation,
)

# Register your models here.
admin.site.register(EveMarketLocation)
admin.site.register(EveMarketContractExpectation)
admin.site.register(EveMarketItemExpectation)
admin.site.register(EveMarketContractResponsibility)
