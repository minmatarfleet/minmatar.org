"""Links to the website (my.minmatar.org) from the backend.

Every link the backend puts in a Discord message, a redirect or a payload is
built here from ``settings.WEB_LINK_URL``, so dev and staging link to their
own site, never to production. (``settings.SITE_URL`` is the backend's own
origin, not the website's.)

The named routes are the website pages other surfaces also open: the desktop
app builds the same paths in ``desktop/src/main/web_routes.js``. Installed
desktop versions can't be changed, so the website keeps these paths working,
or redirects them, when its pages move.
"""

from __future__ import annotations

from django.conf import settings


def web_url() -> str:
    """The website's origin, without a trailing slash."""
    return settings.WEB_LINK_URL.rstrip("/")


def web_link(path: str = "/") -> str:
    """An absolute website URL for a site path such as ``/fleets/upcoming/``."""
    return f"{web_url()}/{path.lstrip('/')}"


def upcoming_fleets_url() -> str:
    return web_link("/fleets/upcoming/")


def fleet_url(fleet_id: int, ended: bool = False) -> str:
    """A fleet's page: upcoming while it can still be joined, else history."""
    section = "history" if ended else "upcoming"
    return web_link(f"/fleets/{section}/{int(fleet_id)}")


def fleet_edit_url(fleet_id: int) -> str:
    return web_link(f"/fleets/upcoming/edit/{int(fleet_id)}")


def fitting_url(fitting_id: int) -> str:
    return web_link(f"/ships/fittings/{int(fitting_id)}")


def doctrine_url(doctrine_id: int) -> str:
    return web_link(f"/ships/doctrines/list/{int(doctrine_id)}")


def new_player_fleet_guide_url() -> str:
    return web_link("/learning/guides/new-player-fleet-guide/")
