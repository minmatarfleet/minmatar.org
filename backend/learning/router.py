from ninja import Router

from learning.endpoints import (
    get_certificate,
    get_certificate_method,
    get_certificate_path,
    get_certificate_spec,
    get_certificates,
    get_certificates_method,
    get_certificates_path,
    get_certificates_spec,
    get_me,
    get_me_method,
    get_me_path,
    get_me_spec,
    get_persona_recommendation,
    get_recommendation_method,
    get_recommendation_path,
    get_recommendation_spec,
    post_complete_learning,
    post_complete_method,
    post_complete_path,
    post_complete_spec,
    post_import,
    post_import_method,
    post_import_path,
    post_import_spec,
    put_persona,
    put_persona_method,
    put_persona_path,
    put_persona_spec,
)

router = Router(tags=["Learning Center"])

# Fixed paths before catch-alls / parameterized routes that could collide.
_ROUTES = (
    (get_me_method, get_me_path, get_me_spec, get_me),
    (
        get_recommendation_method,
        get_recommendation_path,
        get_recommendation_spec,
        get_persona_recommendation,
    ),
    (put_persona_method, put_persona_path, put_persona_spec, put_persona),
    (post_import_method, post_import_path, post_import_spec, post_import),
    (
        post_complete_method,
        post_complete_path,
        post_complete_spec,
        post_complete_learning,
    ),
    (
        get_certificates_method,
        get_certificates_path,
        get_certificates_spec,
        get_certificates,
    ),
    (
        get_certificate_method,
        get_certificate_path,
        get_certificate_spec,
        get_certificate,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
