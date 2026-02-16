from eveonline.models import EveCharacter, EveCorporation


def entity_name_by_id(entity_ids):
    if not entity_ids:
        return {}
    character_names = dict(
        EveCharacter.objects.filter(character_id__in=entity_ids).values_list(
            "character_id", "character_name"
        )
    )
    corporation_names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=entity_ids
        ).values_list("corporation_id", "name")
    )
    result = {}
    for eid in entity_ids:
        if eid in character_names:
            result[eid] = ("character", character_names[eid])
        elif eid in corporation_names:
            result[eid] = ("corporation", corporation_names[eid])
    return result
