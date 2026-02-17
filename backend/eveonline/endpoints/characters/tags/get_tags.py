"""GET /tags - get possible tags for characters."""

from typing import List

from eveonline.endpoints.characters.schemas import CharacterTagResponse
from eveonline.models import EveTag

PATH = "tags"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get possible tags for characters",
    "response": {200: List[CharacterTagResponse]},
}


def get_tags(request):
    tags = EveTag.objects.all()
    return 200, [
        CharacterTagResponse(
            id=tag.id,
            title=tag.title,
            description=tag.description,
            image_name=tag.image_name,
        )
        for tag in tags
    ]
