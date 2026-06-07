"""Map ESI implant type IDs to slot-keyed implant payloads."""

from eveuniverse.models import EveType, EveTypeDogmaAttribute

from market.helpers.pricing import get_prices_by_type_id

ATTRIBUTE_BONUS_SLOTS = (
    ("charismaBonus", "charisma"),
    ("intelligenceBonus", "intelligence"),
    ("memoryBonus", "memory"),
    ("perceptionBonus", "perception"),
    ("willpowerBonus", "willpower"),
)

HARDWIRING_SLOT_PREFIX = "slot"


def _dogma_values_for_type(eve_type: EveType) -> dict[str, float]:
    return {
        row.eve_dogma_attribute.name: row.value
        for row in EveTypeDogmaAttribute.objects.filter(
            eve_type=eve_type
        ).select_related("eve_dogma_attribute")
    }


def attribute_slot_for_type_id(type_id: int) -> str | None:
    """Return attribute slot key (charisma, memory, ...) when applicable."""
    eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
    attrs = _dogma_values_for_type(eve_type)
    for bonus_attr, slot_key in ATTRIBUTE_BONUS_SLOTS:
        if attrs.get(bonus_attr, 0) > 0:
            return slot_key
    return None


def build_slot_keyed_implants(type_ids: list[int]) -> dict[str, dict]:
    """
    Build {slot: {type_id, name}} from a list of implant type IDs.

    Attribute enhancers use named slots; remaining implants use slot6+.
    """
    if not type_ids:
        return {}

    unique_ids = sorted({int(tid) for tid in type_ids})
    result: dict[str, dict] = {}
    hardwiring_counter = 6

    for type_id in unique_ids:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        slot_key = attribute_slot_for_type_id(type_id)
        if not slot_key:
            slot_key = f"{HARDWIRING_SLOT_PREFIX}{hardwiring_counter}"
            hardwiring_counter += 1
        result[slot_key] = {
            "type_id": type_id,
            "name": eve_type.name,
        }

    return result


def build_clone_implant_list(type_ids: list[int]) -> list[dict]:
    """Build [{type_id, type_name, estimated_price_isk}] for clone storage."""
    if not type_ids:
        return []

    unique_ids = sorted({int(tid) for tid in type_ids})
    prices = get_prices_by_type_id(unique_ids)
    implants = []
    for type_id in unique_ids:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        implants.append(
            {
                "type_id": type_id,
                "type_name": eve_type.name,
                "estimated_price_isk": prices.get(type_id, 0),
            }
        )
    return implants


def total_implant_value_isk(implants: list[dict]) -> int:
    return sum(int(item.get("estimated_price_isk") or 0) for item in implants)
