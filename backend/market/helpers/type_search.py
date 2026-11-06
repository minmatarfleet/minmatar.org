"""Type-name search shared by the settings editors."""

from eveuniverse.models import EveType

MIN_QUERY_LENGTH = 2
RESULT_LIMIT = 15


def search_types(query: str, limit: int = RESULT_LIMIT) -> list[EveType]:
    """Published types whose name contains the query, alphabetical."""
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        return []
    return list(
        EveType.objects.filter(name__icontains=query, published=True).order_by(
            "name"
        )[:limit]
    )
