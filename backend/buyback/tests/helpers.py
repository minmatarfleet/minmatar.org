"""Shared fixtures for buyback tests."""

from eveuniverse.models import EveCategory, EveGroup, EveType

BASE_URL = "/api/buyback"


def ensure_type(
    *,
    type_id: int,
    name: str,
    group_id: int,
    group_name: str,
    category_id: int,
    category_name: str,
) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=category_id,
        defaults={"name": category_name, "published": True},
    )
    if category.name != category_name:
        category.name = category_name
        category.save(update_fields=["name"])
    group, _ = EveGroup.objects.get_or_create(
        id=group_id,
        defaults={
            "name": group_name,
            "eve_category": category,
            "published": True,
        },
    )
    if group.name != group_name or group.eve_category_id != category.id:
        group.name = group_name
        group.eve_category = category
        group.save()
    eve_type, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "eve_group": group,
            "published": True,
        },
    )
    if eve_type.name != name or eve_type.eve_group_id != group.id:
        eve_type.name = name
        eve_type.eve_group = group
        eve_type.save()
    return eve_type
