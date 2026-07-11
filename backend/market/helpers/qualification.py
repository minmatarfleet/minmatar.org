from fittings.models import EveDoctrineFitting, EveFitting


def get_qualified_sell_fittings(location):
    """
    Return fittings whose tags overlap the location's market_categories (ANY).
    """
    categories = location.market_categories or []
    if not categories:
        return EveFitting.objects.none()

    category_set = set(categories)
    fitting_ids = []
    for fitting in EveFitting.objects.filter(deleted__isnull=True).only(
        "pk", "tags"
    ):
        tags = fitting.tags or []
        if category_set.intersection(tags):
            fitting_ids.append(fitting.pk)

    return EveFitting.objects.filter(pk__in=fitting_ids).order_by("name")


def get_qualified_contract_fittings(location):
    """
    Return fittings from doctrines assigned to this location.
    """
    fitting_ids = (
        EveDoctrineFitting.objects.filter(doctrine__locations=location)
        .values_list("fitting_id", flat=True)
        .distinct()
    )
    return EveFitting.objects.filter(
        pk__in=fitting_ids, deleted__isnull=True
    ).order_by("name")


def get_all_doctrine_fittings():
    """Return all active fittings assigned to at least one doctrine."""
    fitting_ids = EveDoctrineFitting.objects.values_list(
        "fitting_id", flat=True
    ).distinct()
    return EveFitting.objects.filter(
        deleted__isnull=True, pk__in=fitting_ids
    ).order_by("name")


def get_doctrine_names_by_fitting_id(
    fitting_ids: list[int],
) -> dict[int, list[str]]:
    names_by_fitting: dict[int, list[str]] = {}
    if not fitting_ids:
        return names_by_fitting
    rows = (
        EveDoctrineFitting.objects.filter(fitting_id__in=fitting_ids)
        .select_related("doctrine")
        .order_by("doctrine__name")
        .values_list("fitting_id", "doctrine__name")
    )
    for fitting_id, doctrine_name in rows:
        names_by_fitting.setdefault(fitting_id, []).append(doctrine_name)
    return names_by_fitting


def get_non_doctrine_fittings():
    """Return all active fittings that are not assigned to any doctrine."""
    doctrine_fitting_ids = EveDoctrineFitting.objects.values_list(
        "fitting_id", flat=True
    ).distinct()
    return (
        EveFitting.objects.filter(deleted__isnull=True)
        .exclude(pk__in=doctrine_fitting_ids)
        .order_by("name")
    )


def get_qualified_non_doctrine_sell_fittings(location):
    """
    Return non-doctrine fittings qualified for sell orders at this location.

    When market categories are configured, only tag-qualified fittings are
    returned and doctrine fittings are excluded even if they share tags.
    """
    doctrine_fitting_ids = EveDoctrineFitting.objects.values_list(
        "fitting_id", flat=True
    ).distinct()
    if not (location.market_categories or []):
        return get_non_doctrine_fittings()
    return get_qualified_sell_fittings(location).exclude(
        pk__in=doctrine_fitting_ids
    )
