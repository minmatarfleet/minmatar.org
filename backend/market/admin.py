from django.contrib import admin
from market.models import (
    EveMarketContractExpectation,
    EveMarketItemExpectation,
)

# Register your models here.
admin.site.register(EveMarketContractExpectation)
admin.site.register(EveMarketItemExpectation)
