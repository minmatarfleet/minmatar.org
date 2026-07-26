"""Lightweight CORS for browser clients calling the API from the web app origin.

django-cors-headers is not a dependency; Ninja routes only register their HTTP
methods, so cross-origin POSTs fail OPTIONS with 405 without this middleware.
"""

from django.conf import settings
from django.http import HttpResponse


def _allowed_origins() -> set[str]:
    configured = getattr(settings, "CORS_ALLOWED_ORIGINS", None)
    if configured:
        return {str(o).rstrip("/") for o in configured if o}
    origins = {
        "http://localhost:4321",
        "https://my.minmatar.org",
        "https://minmatar.org",
    }
    web_link = getattr(settings, "WEB_LINK_URL", None)
    if web_link:
        origins.add(str(web_link).rstrip("/"))
    return origins


class SimpleCorsMiddleware:
    """Answer CORS preflight and attach Allow-* headers for allowed Origins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        if (
            request.method == "OPTIONS"
            and origin
            and origin.rstrip("/") in _allowed_origins()
        ):
            response = HttpResponse(status=204)
            self._apply_cors(response, origin)
            return response

        response = self.get_response(request)
        if origin and origin.rstrip("/") in _allowed_origins():
            self._apply_cors(response, origin)
        return response

    @staticmethod
    def _apply_cors(response, origin: str) -> None:
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept"
        )
        response["Access-Control-Max-Age"] = "86400"
        # Merge Vary: Origin with any existing Vary values.
        vary = response.get("Vary")
        if vary:
            parts = {p.strip() for p in vary.split(",") if p.strip()}
            parts.add("Origin")
            response["Vary"] = ", ".join(sorted(parts))
        else:
            response["Vary"] = "Origin"
