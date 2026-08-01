from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import BuybackAcceptedItem, EveBuybackSettings


@admin.register(EveBuybackSettings)
class EveBuybackSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "assignee_name",
        "location",
        "active",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "active",
                    "assignee_name",
                    "location",
                    "leading_text",
                    "discord_thread_url",
                )
            },
        ),
        (
            "What we buy",
            {
                "fields": (
                    "accepted_categories",
                    "rate_rules",
                    "exclusions",
                ),
                "description": (
                    "Category bullets are summary copy. Appraisal acceptance "
                    "is controlled by Buyback accepted items."
                ),
            },
        ),
    )


@admin.register(BuybackAcceptedItem)
class BuybackAcceptedItemAdmin(admin.ModelAdmin):
    list_display = ("eve_type", "category", "active", "created_at")
    list_filter = ("category", "active")
    search_fields = ("eve_type__name",)
    autocomplete_fields = ("eve_type",)
    list_editable = ("active",)

    def save_model(self, request, obj, form, change):
        if obj.active and not obj.location_id:
            raise ValidationError("Active buyback requires a location.")
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return not EveBuybackSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
