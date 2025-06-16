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
    def log(cls, detail: str, log_data: str | Exception | None):
        response = cls(detail=detail, id=create_error_id())
        if log_data is None:
            logger.error("%s (%s)", detail, response.id)
        elif isinstance(log_data, Exception):
            logger.error("%s (%s)", detail, response.id, exc_info=log_data)
        else:
            logger.error("%s : %s (%s)", detail, str(log_data), response.id)
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
