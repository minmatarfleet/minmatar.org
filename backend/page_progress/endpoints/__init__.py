from ninja import Router

from page_progress.endpoints.get_page_progress import (
    METHOD as get_status_method,
    PATH as get_status_path,
    ROUTE_SPEC as get_status_spec,
    get_page_progress,
)
from page_progress.endpoints.post_import_pages import (
    METHOD as post_import_method,
    PATH as post_import_path,
    ROUTE_SPEC as post_import_spec,
    post_import_pages,
)
from page_progress.endpoints.post_page_ack import (
    METHOD as post_ack_method,
    PATH as post_ack_path,
    ROUTE_SPEC as post_ack_spec,
    post_page_ack,
)
from page_progress.endpoints.post_section_read import (
    METHOD as post_section_method,
    PATH as post_section_path,
    ROUTE_SPEC as post_section_spec,
    post_section_read,
)

router = Router(tags=["Page Progress"])

# Fixed paths before "{page_key}" catch-alls.
_ROUTES = (
    (
        post_import_method,
        post_import_path,
        post_import_spec,
        post_import_pages,
    ),
    (
        post_section_method,
        post_section_path,
        post_section_spec,
        post_section_read,
    ),
    (post_ack_method, post_ack_path, post_ack_spec, post_page_ack),
    (get_status_method, get_status_path, get_status_spec, get_page_progress),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
