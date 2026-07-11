from django.core.exceptions import ValidationError
from django.db import models

from app.models import MinmatarSoftDeleteModel
from safedelete.config import SOFT_DELETE


class EveAlliance(models.Model):
    """Alliance model"""

    alliance_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return str(self.name)


class EveLocation(MinmatarSoftDeleteModel):
    """An alliance location for freight, market or staging"""

    location_id = models.BigIntegerField(primary_key=True)
    location_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32)
    region_id = models.BigIntegerField(null=True)
    is_structure = models.BooleanField(
        default=False,
        help_text="True if location_id is an Upwell structure (use structure markets API). False for NPC station (use region orders API).",
    )
    market_active = models.BooleanField(default=False)
    prices_active = models.BooleanField(default=False)
    price_baseline = models.BooleanField(
        default=False,
        help_text="At most one location may be the price baseline. "
        "Used as the reference for markup calculations.",
    )
    freight_active = models.BooleanField(default=False)
    staging_active = models.BooleanField(default=False)
    market_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Fitting tags that qualify sell-order fittings at this location (ANY match).",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["price_baseline"],
                condition=models.Q(price_baseline=True)
                & models.Q(deleted__isnull=True),
                name="unique_price_baseline_location",
            ),
        ]

    def _clear_operational_flags_for_soft_delete(self) -> None:
        self.price_baseline = False
        self.market_active = False
        self.prices_active = False
        self.freight_active = False
        self.staging_active = False

    def delete(self, force_policy=None, **kwargs):
        policy = (
            self._safedelete_policy if force_policy is None else force_policy
        )
        if policy == SOFT_DELETE:
            self._clear_operational_flags_for_soft_delete()
        return super().delete(force_policy=force_policy, **kwargs)

    @staticmethod
    def coerce_market_categories(raw):
        # Circular import: fittings.models imports EveLocation from this module.
        # pylint: disable=import-outside-toplevel
        from fittings.models import FittingTag

        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValidationError("market_categories must be a list")
        allowed = {choice.value for choice in FittingTag}
        seen = set()
        out = []
        for item in raw:
            if not isinstance(item, str):
                raise ValidationError("each market category must be a string")
            if item not in allowed:
                raise ValidationError(f"invalid market category: {item!r}")
            if item not in seen:
                seen.add(item)
                out.append(item)
        out.sort()
        return out

    def clean(self):
        try:
            self.market_categories = self.coerce_market_categories(
                self.market_categories
            )
        except ValidationError as exc:
            raise ValidationError(
                {"market_categories": list(exc.messages)}
            ) from exc

        if self.price_baseline:
            dup = (
                EveLocation.objects.filter(price_baseline=True)
                .exclude(pk=self.pk)
                .first()
            )
            if dup:
                raise ValidationError(
                    f"Only one location can be the price baseline. "
                    f'"{dup.location_name}" already has it enabled.'
                )

    def save(self, *args, **kwargs):
        self.market_categories = self.coerce_market_categories(
            self.market_categories
        )
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.location_name)
