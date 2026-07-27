"""GET /certificates/{slug} — one published certificate with ordered learnings."""

from app.errors import ErrorResponse
from learning.schemas import CertificateSchema
from learning.serialization import (
    get_published_certificate,
    serialize_certificate,
)

PATH = "certificates/{slug}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get a published Learning Center certificate.",
    "response": {200: CertificateSchema, 404: ErrorResponse},
}


def get_certificate(request, slug: str):
    certificate = get_published_certificate(slug)
    if certificate is None:
        return 404, ErrorResponse(detail="Certificate not found.")
    return serialize_certificate(certificate)
