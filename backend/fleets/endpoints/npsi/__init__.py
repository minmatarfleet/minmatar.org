"""NPSI calendar ingest Discord actions."""

from fleets.endpoints.npsi.post_discord_create import (
    PATH as post_discord_create_path,
    ROUTE_SPEC as post_discord_create_spec,
    post_npsi_discord_create,
    METHOD as post_discord_create_method,
)
from fleets.endpoints.npsi.post_discord_post import (
    PATH as post_discord_post_path,
    ROUTE_SPEC as post_discord_post_spec,
    post_npsi_discord_post,
    METHOD as post_discord_post_method,
)
from fleets.endpoints.npsi.post_discord_preping import (
    PATH as post_discord_preping_path,
    ROUTE_SPEC as post_discord_preping_spec,
    post_npsi_discord_preping,
    METHOD as post_discord_preping_method,
)
from fleets.endpoints.npsi.post_discord_tracking import (
    PATH as post_discord_tracking_path,
    ROUTE_SPEC as post_discord_tracking_spec,
    post_npsi_discord_tracking,
    METHOD as post_discord_tracking_method,
)
from fleets.endpoints.npsi import sources

_ROUTES = (
    (
        sources.LIST_METHOD,
        sources.LIST_PATH,
        sources.LIST_SPEC,
        sources.get_npsi_sources,
    ),
    (
        sources.CREATE_METHOD,
        sources.CREATE_PATH,
        sources.CREATE_SPEC,
        sources.post_npsi_source,
    ),
    (
        sources.PATCH_METHOD,
        sources.PATCH_PATH,
        sources.PATCH_SPEC,
        sources.patch_npsi_source,
    ),
    (
        sources.EVENTS_METHOD,
        sources.EVENTS_PATH,
        sources.EVENTS_SPEC,
        sources.get_npsi_source_events,
    ),
    (
        post_discord_create_method,
        post_discord_create_path,
        post_discord_create_spec,
        post_npsi_discord_create,
    ),
    (
        post_discord_post_method,
        post_discord_post_path,
        post_discord_post_spec,
        post_npsi_discord_post,
    ),
    (
        post_discord_preping_method,
        post_discord_preping_path,
        post_discord_preping_spec,
        post_npsi_discord_preping,
    ),
    (
        post_discord_tracking_method,
        post_discord_tracking_path,
        post_discord_tracking_spec,
        post_npsi_discord_tracking,
    ),
)

__all__ = ["_ROUTES"]
