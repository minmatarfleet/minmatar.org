"""GET /training/characters/{character_id}/accounts - the accounts a character can move to."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import AccountOptionsResponse

PATH = "/characters/{character_id}/accounts"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "The accounts a character can move to",
    "auth": AuthBearer(),
    "response": {200: AccountOptionsResponse, 404: ErrorResponse},
}


def get_accounts(request, character_id: int):
    try:
        return 200, training.account_options(request.user, character_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
