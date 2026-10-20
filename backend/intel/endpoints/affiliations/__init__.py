"""The affiliation database's API, one endpoint per module."""

from ninja import Router

from intel.endpoints.affiliations import (
    get_bloc,
    get_blocs,
    get_entity,
    get_members,
    get_review,
    get_search,
    patch_bloc,
    post_affiliation,
    post_bloc_merge,
    post_decision,
    post_investigate,
)


def _router(*modules) -> Router:
    router = Router(tags=["Intel"])
    for module in modules:
        for handler in vars(module).values():
            route = getattr(handler, "route", None)
            if callable(handler) and route:
                method, path, spec = route
                getattr(router, method)(path, **spec)(handler)
    return router


affiliations_router = _router(
    get_review, get_members, post_affiliation, post_decision
)
blocs_router = _router(get_blocs, get_bloc, patch_bloc, post_bloc_merge)
# /search before /{kind}/{eve_id} so "search" isn't read as a kind.
entities_router = _router(get_search, get_entity, post_investigate)

__all__ = ["affiliations_router", "blocs_router", "entities_router"]
