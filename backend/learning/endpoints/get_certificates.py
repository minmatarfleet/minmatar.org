"""GET /certificates — published certificates for an optional persona."""

from learning.helpers import certificates_for_persona
from learning.schemas import CertificateSchema
from learning.serialization import serialize_certificate

PATH = "certificates"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List published Learning Center certificates.",
    "response": {200: list[CertificateSchema]},
}


def get_certificates(request, persona: str = ""):
    persona_key = (persona or "").strip() or None
    certificates = certificates_for_persona(persona_key)
    return [serialize_certificate(c) for c in certificates]
