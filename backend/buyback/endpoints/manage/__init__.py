"""Buyback settings editor."""

from ninja import Router

from buyback.endpoints.manage.get_manage_settings import (
    METHOD as get_manage_settings_method,
    PATH as get_manage_settings_path,
    ROUTE_SPEC as get_manage_settings_spec,
    get_manage_settings,
)
from buyback.endpoints.manage.patch_manage_settings import (
    METHOD as patch_manage_settings_method,
    PATH as patch_manage_settings_path,
    ROUTE_SPEC as patch_manage_settings_spec,
    patch_manage_settings,
)
from buyback.endpoints.manage.post_manage_item import (
    METHOD as post_manage_item_method,
    PATH as post_manage_item_path,
    ROUTE_SPEC as post_manage_item_spec,
    post_manage_item,
)
from buyback.endpoints.manage.patch_manage_item import (
    METHOD as patch_manage_item_method,
    PATH as patch_manage_item_path,
    ROUTE_SPEC as patch_manage_item_spec,
    patch_manage_item,
)
from buyback.endpoints.manage.delete_manage_item import (
    METHOD as delete_manage_item_method,
    PATH as delete_manage_item_path,
    ROUTE_SPEC as delete_manage_item_spec,
    delete_manage_item,
)
from buyback.endpoints.manage.get_manage_types import (
    METHOD as get_manage_types_method,
    PATH as get_manage_types_path,
    ROUTE_SPEC as get_manage_types_spec,
    get_manage_types,
)

router = Router(tags=["Buyback"])

_ROUTES = (
    (
        get_manage_settings_method,
        get_manage_settings_path,
        get_manage_settings_spec,
        get_manage_settings,
    ),
    (
        patch_manage_settings_method,
        patch_manage_settings_path,
        patch_manage_settings_spec,
        patch_manage_settings,
    ),
    (
        post_manage_item_method,
        post_manage_item_path,
        post_manage_item_spec,
        post_manage_item,
    ),
    (
        patch_manage_item_method,
        patch_manage_item_path,
        patch_manage_item_spec,
        patch_manage_item,
    ),
    (
        delete_manage_item_method,
        delete_manage_item_path,
        delete_manage_item_spec,
        delete_manage_item,
    ),
    (
        get_manage_types_method,
        get_manage_types_path,
        get_manage_types_spec,
        get_manage_types,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
