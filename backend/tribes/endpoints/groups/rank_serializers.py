"""Serialize tribe group ranks for API responses."""

from tribes.endpoints.groups.schemas import TribeGroupRankSchema
from tribes.models import TribeGroup


def serialize_tribe_group_ranks(tg: TribeGroup) -> list[TribeGroupRankSchema]:
    return [
        TribeGroupRankSchema(
            id=rank.pk,
            code=rank.code,
            name=rank.name,
            sort_order=rank.sort_order,
        )
        for rank in tg.ranks.all()
    ]
