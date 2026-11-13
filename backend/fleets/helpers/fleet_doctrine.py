"""Which doctrines a fleet may pick."""

from app.errors import ErrorResponse
from fittings.models import EveDoctrine


def doctrine_choice_error(doctrine_id) -> tuple[int, ErrorResponse] | None:
    """A 400 when a fleet picks a doctrine that is missing or removed."""
    if not doctrine_id:
        return None
    doctrine = EveDoctrine.all_objects.filter(id=doctrine_id).first()
    if doctrine is None:
        return 400, ErrorResponse.new("Doctrine does not exist")
    if doctrine.deleted is not None:
        return 400, ErrorResponse.new(
            f"{doctrine.name} has been removed. Pick a current doctrine."
        )
    return None
