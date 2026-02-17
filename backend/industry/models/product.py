from django.core.exceptions import ValidationError
from django.db import models


class Strategy(models.TextChoices):
    """
    How we source this type. Default is imported; no blueprint → harvested;
    has blueprint → can be produced.
    """

    IMPORTED = "imported", "Imported"
    HARVESTED = "harvested", "Harvested"
    PRODUCED = "produced", "Produced"


class IndustryProduct(models.Model):
    """
    An Eve type we track as an industry product.

    - **Strategy**: How we source it. Default **imported**. Types without a
      blueprint (ore, ice, etc.) can be **harvested**. Types with a blueprint
      can be **produced** (we build them).

    Industry product flow (for ordered / top-level products):
    - **Imported** or **harvested**: we source by importing or harvesting; no expansion.
    - **Produced**: we build it. Expand to the direct industry products (components)
      that make it up; those are treated as import at this step. Any of those
      components can themselves be produced, and we repeat. Use resolve_order_to_imports()
      / resolve_product_to_imports() in industry.helpers.type_breakdown to compute
      the final import list.

    **volume**: Property returning the type's volume in m³ (from eve_type.volume or
    packaged_volume). Requires eve_type to be loaded (e.g. select_related("eve_type")).

    **blueprint_or_reaction_type_id**: Property returning the Eve type ID of the
    blueprint or reaction that produces this type, or None if it has no recipe.

    breakdown: optional cached nested component tree (root quantity=1). Use
    get_breakdown_for_industry_product() to fetch or compute (and store) it.

    **supplied_for**: When this product is a direct component of others (we build them),
    those parent products are listed here. Updated on save when a produced product
    is saved: we deconstruct to direct components, ensure IndustryProduct exists for
    each, and set each component's supplied_for to include this product.
    """

    eve_type = models.OneToOneField(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="industry_product",
    )
    strategy = models.CharField(
        max_length=16,
        choices=Strategy.choices,
        default=Strategy.IMPORTED,
    )
    breakdown = models.JSONField(
        null=True,
        blank=True,
        help_text="Full-depth nested component tree (root quantity=1). From get_breakdown_for_industry_product.",
    )
    supplied_for = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="supplies",
        help_text="Industry products that use this one as a direct component (this is supplied for those).",
    )

    class Meta:
        verbose_name = "industry product"
        verbose_name_plural = "industry products"

    def __str__(self):
        return f"{self.eve_type.name} ({self.get_strategy_display()})"

    def clean(self):
        super().clean()
        if self.strategy == Strategy.PRODUCED and self.eve_type_id:
            from industry.helpers.type_breakdown import (  # pylint: disable=import-outside-toplevel
                get_blueprint_or_reaction_type_id,
            )

            if get_blueprint_or_reaction_type_id(self.eve_type) is None:
                raise ValidationError(
                    {
                        "strategy": "Cannot mark as produced: this type has no "
                        "blueprint or reaction (e.g. ore, ice). Use imported or harvested."
                    }
                )

    @property
    def volume(self):
        """Volume in m³ from the Eve type (volume or packaged_volume)."""
        if self.eve_type_id is None:
            return None
        eve_type = self.eve_type
        return getattr(eve_type, "packaged_volume", None) or getattr(
            eve_type, "volume", None
        )

    @property
    def blueprint_or_reaction_type_id(self):
        """
        Eve type ID of the blueprint or reaction that produces this product's type,
        or None if it has no recipe (imported/harvested).
        """
        if not self.eve_type_id:
            return None
        from industry.helpers.type_breakdown import (  # pylint: disable=import-outside-toplevel
            get_blueprint_or_reaction_type_id,
        )

        return get_blueprint_or_reaction_type_id(self.eve_type)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if not self.eve_type_id:
            return
        # Defer import to avoid circular import (type_breakdown imports industry.models).
        from industry.helpers.type_breakdown import (  # pylint: disable=import-outside-toplevel
            get_direct_components,
        )

        if self.strategy == Strategy.PRODUCED:
            # Deconstruct: ensure IndustryProduct exists for each direct component
            # and point those components at us (supplied_for).
            direct = get_direct_components(self.eve_type, quantity=1)
            current_component_products = set()
            for direct_item in direct:
                comp_eve_type = direct_item[0]
                comp_product = IndustryProduct.objects.get_or_create(
                    eve_type=comp_eve_type,
                    defaults={"strategy": Strategy.IMPORTED},
                )[0]
                comp_product.supplied_for.add(self)
                current_component_products.add(comp_product.id)
            # Remove self from any product that used to be our component but isn't.
            # If that product is then no longer supplied for anything and isn't produced, remove it.
            for comp in list(self.supplies.all()):
                if comp.id not in current_component_products:
                    comp.supplied_for.remove(self)
                    if (
                        comp.strategy != Strategy.PRODUCED
                        and not comp.supplied_for.exists()
                    ):
                        comp.delete()
        else:
            # No longer produced: remove us from every component's supplied_for.
            # If a component is then no longer supplied for anything and isn't produced, remove it.
            for comp in list(self.supplies.all()):
                comp.supplied_for.remove(self)
                if (
                    comp.strategy != Strategy.PRODUCED
                    and not comp.supplied_for.exists()
                ):
                    comp.delete()
