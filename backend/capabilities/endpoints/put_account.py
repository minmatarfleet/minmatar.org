"""PUT /training/characters/{character_id}/account - put a character on another account, a new one, or none."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import (
    AccountMoveRequest,
    TrainingChangeResponse,
)

PATH = "/characters/{character_id}/account"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Put a character on another account, a new one, or none",
    "auth": AuthBearer(),
    "response": {200: TrainingChangeResponse, 404: ErrorResponse},
}


def put_account(request, character_id: int, payload: AccountMoveRequest):
    try:
        training.move_character(
            request.user,
            character_id,
            payload.account,
            new_account=payload.new_account,
        )
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return 200, TrainingChangeResponse(ok=True)
