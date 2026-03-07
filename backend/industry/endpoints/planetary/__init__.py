"""Planetary (PI) router: harvest overview/drill-down, production overview/drill-down, planet summary."""

from ninja import Router

from industry.endpoints.planetary.get_harvest import (
    ROUTE_SPEC as get_harvest_spec,
    get_harvest,
    METHOD as get_harvest_method,
)
from industry.endpoints.planetary.get_harvest_type_id import (
    PATH as get_harvest_type_id_path,
    ROUTE_SPEC as get_harvest_type_id_spec,
    get_harvest_type_id,
    METHOD as get_harvest_type_id_method,
)
from industry.endpoints.planetary.get_production import (
    ROUTE_SPEC as get_production_spec,
    get_production,
    METHOD as get_production_method,
)
from industry.endpoints.planetary.get_production_type_id import (
    PATH as get_production_type_id_path,
    ROUTE_SPEC as get_production_type_id_spec,
    get_production_type_id,
    METHOD as get_production_type_id_method,
)
from industry.endpoints.planetary.get_planets import (
    ROUTE_SPEC as get_planets_spec,
    get_planets,
    METHOD as get_planets_method,
)

router = Router(tags=["Industry - Planetary"])

router.get("harvest", **get_harvest_spec)(get_harvest)
getattr(router, get_harvest_type_id_method)(
    f"harvest/{get_harvest_type_id_path}",
    **get_harvest_type_id_spec,
)(get_harvest_type_id)

router.get("production", **get_production_spec)(get_production)
getattr(router, get_production_type_id_method)(
    f"production/{get_production_type_id_path}",
    **get_production_type_id_spec,
)(get_production_type_id)

router.get("planets", **get_planets_spec)(get_planets)

__all__ = ["router"]
