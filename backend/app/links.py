"""Links to the website (the Astro frontend), built from WEB_LINK_URL.

Use site_url() for every link the backend hands out (Discord messages, MOTDs,
redirects, payloads) so dev and staging point at their own frontend, never at
production. ``settings.SITE_URL`` is the backend's own origin, not the
website's. PRODUCTION_SITE_URL is only for places that must name production
regardless of environment (CORS defaults, outbound User-Agent strings).

The named routes below are the website pages other surfaces also open: the
desktop app builds the same paths in ``desktop/src/main/web_routes.js``.
Installed desktop versions can't be changed, so the website keeps these paths
working, or redirects them, when its pages move.
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


def upcoming_fleets_url() -> str:
    return site_url("/fleets/upcoming/")


def fleet_url(fleet_id: int, ended: bool = False) -> str:
    """A fleet's page: upcoming while it can still be joined, else history."""
    section = "history" if ended else "upcoming"
    return site_url(f"/fleets/{section}/{int(fleet_id)}")


def fleet_edit_url(fleet_id: int) -> str:
    return site_url(f"/fleets/upcoming/edit/{int(fleet_id)}")


def fitting_url(fitting_id: int) -> str:
    return site_url(f"/ships/fittings/{int(fitting_id)}")


def doctrine_url(doctrine_id: int) -> str:
    return site_url(f"/ships/doctrines/list/{int(doctrine_id)}")


def new_player_fleet_guide_url() -> str:
    return site_url("/learning/guides/new-player-fleet-guide/")


def first_fleet_guide_url() -> str:
    return site_url("/learning/guides/onboarding-first-fleet/")
