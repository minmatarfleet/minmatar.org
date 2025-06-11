import logging

from pydantic import BaseModel
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """API error response"""

    detail: str
    id: str | None = None

    @classmethod
    def new(cls, detail: str):
        return cls(detail=detail, id=create_error_id())

    @classmethod
    def log(cls, detail: str, log_message: str = None):
        response = cls(detail=detail, id=create_error_id())
        logger.error("%s : %s (%s)", detail, log_message, response.id)
        return response


def create_error_id():
    """
    Make a random error ID in the form `xxxxx-xxxxx` to be used for debugging

    Easily-mistaken characters are excluded from the ID.
    """
    allowed_chars = "ACDEFGHJKLMNPRTUVWXY345679"
    r1 = get_random_string(length=5, allowed_chars=allowed_chars)
    r2 = get_random_string(length=5, allowed_chars=allowed_chars)
    return f"{r1}-{r2}"
