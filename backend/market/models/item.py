import re
from collections import defaultdict

from django.db import models
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone

from eveuniverse.models import EveType
from eveonline.models import EveLocation
from fittings.models import EveFitting

from market.models.contract import EveMarketContractExpectation


class EveTypeWithSellOrdersManager(models.Manager):
    """Return only EveTypes that have at least one EveMarketItemOrder."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                Exists(
                    EveMarketItemOrder.objects.filter(item_id=OuterRef("pk"))
                )
            )
        )


class EveTypeWithSellOrders(EveType):
    """
    Proxy for EveType limited to types we have sell orders for.
    Used in admin as the "Market sell orders" entry point.
    """

    class Meta:
        proxy = True
        verbose_name = "EVE type (with sell orders)"
        verbose_name_plural = "EVE types (with sell orders)"

    objects = EveTypeWithSellOrdersManager()


class EveMarketItemExpectation(models.Model):
    """
    Seed definition: track a target quantity of an EVE type (e.g. 1000 missiles)
    at a location, measured by current sell orders.
    """

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")

    @property
    def current_quantity(self):
        """Total quantity on sell orders for this item at this location."""
        result = EveMarketItemOrder.objects.filter(
            item=self.item,
            location=self.location,
            is_buy_order=False,
        ).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def desired_quantity(self):
        return self.quantity

    @property
    def is_fulfilled(self):
        return self.current_quantity >= self.desired_quantity

    @property
    def is_understocked(self):
        understocked_percentage = 0.5
        return (
            self.current_quantity
            < self.desired_quantity * understocked_percentage
        )


class EveMarketBuyOrderExpectation(models.Model):
    """Target quantity of a buy order for an item at a location."""

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    class Meta:
        unique_together = [["item", "location"]]

    def __str__(self):
        return str(f"{self.item.name} buy - {self.location.location_name}")

    @property
    def current_quantity(self):
        result = EveMarketItemOrder.objects.filter(
            item=self.item,
            location=self.location,
            is_buy_order=True,
        ).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def desired_quantity(self):
        return self.quantity

    @property
    def is_fulfilled(self):
        return self.current_quantity >= self.desired_quantity

    @property
    def is_understocked(self):
        understocked_percentage = 0.5
        return (
            self.current_quantity
            < self.desired_quantity * understocked_percentage
        )


class EveMarketItemOrder(models.Model):
    """One row per market order; order_id from ESI (when present) avoids duplicate imports."""

    order_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="ESI order_id when returned by structure markets; prevents duplicate imports.",
    )
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    is_buy_order = models.BooleanField(
        default=False,
        help_text="True if this is a buy order, False for sell order.",
    )
    issuer_external_id = models.BigIntegerField(null=True, blank=True)
    imported_by_task_uid = models.CharField(
        max_length=64, null=True, blank=True
    )
    imported_page = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="1-based ESI page this order was imported from (for debugging).",
    )
    issued = models.DateTimeField(
        null=True,
        blank=True,
        help_text="ESI order issued timestamp (for expiry guard on inferred sales).",
    )
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ESI order duration in days (for expiry guard on inferred sales).",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=["location", "imported_by_task_uid"],
                name="market_itemorder_loc_task",
            ),
            models.Index(
                fields=["location", "item"],
                name="market_itemorder_loc_item",
            ),
            models.Index(
                fields=["location", "item", "is_buy_order"],
                name="market_itemorder_loc_item_buy",
            ),
        ]

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")


class EveMarketItemTransaction(models.Model):
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()
    sell_date = models.DateTimeField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")


def parse_eft_items(eft_format):
    """
    Parse an EFT-format fitting string and return a dict of {item_name: quantity}.
    Includes the ship (qty 1) and all modules, rigs, charges, and cargo.
    """
    lines = eft_format.strip().split("\n")
    if not lines:
        return {}

    items = defaultdict(int)

    # First line: [ShipName, Fitting name]
    header = lines[0].strip()
    ship_name = header.split(",")[0].strip().strip("[]")
    if ship_name:
        items[ship_name] += 1

    cargo_re = re.compile(r"^(.+?)\s+x(\d+)$")

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("[Empty "):
            continue

        m = cargo_re.match(line)
        if m:
            items[m.group(1).strip()] += int(m.group(2))
        else:
            items[line] += 1

    return dict(items)


class EveMarketFittingExpectation(models.Model):
    """
    Track a target number of a fitting at a location.  The fitting is
    decomposed into its ship + modules so each component appears as an
    item-level expectation on the market.
    """

    fitting = models.ForeignKey(EveFitting, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    class Meta:
        unique_together = [["fitting", "location"]]

    def __str__(self):
        return f"{self.fitting.name} x{self.quantity} - {self.location.location_name}"

    def get_item_quantities(self):
        """
        Decompose the fitting and multiply by the expectation quantity.
        Returns {item_name: total_quantity_needed}.
        """
        per_fit = parse_eft_items(self.fitting.eft_format)
        return {name: qty * self.quantity for name, qty in per_fit.items()}


_STRUCTURAL_CATEGORIES = frozenset({"Ship", "Module", "Subsystem"})


def _get_consumable_items(fitting):
    """
    Parse a fitting's EFT and return ``{item_name: qty}`` for consumable
    items only — charges, drones, nanite paste, etc.  The hull, modules,
    rigs, and subsystems are excluded.

    Items whose EveType cannot be resolved are also excluded (we need a
    known category to classify them).
    """
    all_items = parse_eft_items(fitting.eft_format)
    if not all_items:
        return {}

    type_categories = dict(
        EveType.objects.filter(
            name__in=list(all_items.keys()),
        ).values_list("name", "eve_group__eve_category__name")
    )

    return {
        name: qty
        for name, qty in all_items.items()
        if name in type_categories
        and type_categories[name] not in _STRUCTURAL_CATEGORIES
    }


def get_effective_item_expectations(location):
    """
    Combine fitting-derived expectations and contract consumables, with manual
    item expectations (pinned) overriding fitting-derived quantities for those
    items. Pinned items are excluded from fitting piggyback.
    """
    pinned = {}
    for exp in EveMarketItemExpectation.objects.filter(
        location=location
    ).select_related("item"):
        pinned[exp.item.name] = exp.quantity

    pinned_names = set(pinned.keys())
    effective = defaultdict(int)

    for fexp in EveMarketFittingExpectation.objects.filter(
        location=location
    ).select_related("fitting"):
        for name, qty in fexp.get_item_quantities().items():
            if name in pinned_names:
                continue
            effective[name] = max(effective[name], qty)

    for cexp in EveMarketContractExpectation.objects.filter(
        location=location
    ).select_related("fitting"):
        consumables = _get_consumable_items(cexp.fitting)
        for name, qty in consumables.items():
            if name in pinned_names:
                continue
            total = qty * cexp.quantity
            effective[name] = max(effective[name], total)

    for name, qty in pinned.items():
        effective[name] = qty

    return dict(effective)


def get_effective_item_expectations_bulk(locations):
    """
    Like get_effective_item_expectations but for many locations at once.
    Returns {location.pk: {item_name: quantity}}.
    """
    location_list = list(locations)
    if not location_list:
        return {}

    location_pks = [location.pk for location in location_list]
    effective_by_location = {
        location_pk: defaultdict(int) for location_pk in location_pks
    }
    pinned_by_location = {location_pk: {} for location_pk in location_pks}

    for exp in EveMarketItemExpectation.objects.filter(
        location_id__in=location_pks
    ).select_related("item"):
        pinned_by_location[exp.location_id][exp.item.name] = exp.quantity

    for fexp in EveMarketFittingExpectation.objects.filter(
        location_id__in=location_pks
    ).select_related("fitting"):
        location_effective = effective_by_location[fexp.location_id]
        pinned_names = pinned_by_location[fexp.location_id]
        for name, qty in fexp.get_item_quantities().items():
            if name in pinned_names:
                continue
            location_effective[name] = max(location_effective[name], qty)

    for cexp in EveMarketContractExpectation.objects.filter(
        location_id__in=location_pks
    ).select_related("fitting"):
        location_effective = effective_by_location[cexp.location_id]
        pinned_names = pinned_by_location[cexp.location_id]
        consumables = _get_consumable_items(cexp.fitting)
        for name, qty in consumables.items():
            if name in pinned_names:
                continue
            total = qty * cexp.quantity
            location_effective[name] = max(location_effective[name], total)

    for location_pk, pinned in pinned_by_location.items():
        location_effective = effective_by_location[location_pk]
        for name, qty in pinned.items():
            location_effective[name] = qty

    return {
        location_pk: dict(effective)
        for location_pk, effective in effective_by_location.items()
    }
