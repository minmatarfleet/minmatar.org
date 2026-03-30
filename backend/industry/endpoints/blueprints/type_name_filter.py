"""Filter blueprint querysets by Eve type name (case-insensitive substring)."""

from django.db.models import Subquery
from eveuniverse.models import EveType


def filter_queryset_by_type_name_icontains(queryset, search: str):
    """Restrict blueprint rows to types whose name contains ``search``."""
    type_ids = EveType.objects.filter(name__icontains=search).values("id")
    return queryset.filter(type_id__in=Subquery(type_ids))
