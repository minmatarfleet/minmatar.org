"""/api/exits: departures from tracked corporations and their flags (#3198)."""

from ninja import Router

from exits.endpoints import (
    get_departures,
    post_departure_answers,
    post_flag_clear,
)

router = Router(tags=["Exits"])

for module in (get_departures, post_departure_answers, post_flag_clear):
    handler = getattr(module, module.__name__.rsplit(".", 1)[1])
    getattr(router, module.METHOD)(module.PATH, **module.ROUTE_SPEC)(handler)
