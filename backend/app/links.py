"""Links to the website (the Astro frontend), built from WEB_LINK_URL.

Use site_url() for every link the backend hands out (Discord messages, MOTDs,
redirects) so dev and staging point at their own frontend. PRODUCTION_SITE_URL
is only for places that must name production regardless of environment
(CORS defaults, outbound User-Agent strings).
"""

from django.conf import settings

PRODUCTION_SITE_URL = "https://my.minmatar.org"


def site_url(path: str = "") -> str:
    """Absolute frontend URL for ``path`` ("/fleets/1" or "fleets/1").

    With no path, returns the base URL without a trailing slash.
    """
    base = settings.WEB_LINK_URL.rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"
