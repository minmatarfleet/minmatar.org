"""
Patches for django-esi views.

``esi.views.receive_callback`` slices ``request.session.session_key[:5]``
for logging. If the session has no key yet (e.g. a fresh/anonymous session
that has not been saved), ``session_key`` is ``None`` and the slice raises
``TypeError: 'NoneType' object is not subscriptable`` (REST-API-A2).

We wrap the view so a session key always exists before the original view
(and its logging) runs.
"""

import esi.views

_PATCHED_ATTR = "_minmatar_session_key_patched"


def patch_esi_receive_callback() -> None:
    """Ensure ``request.session.session_key`` is set before django-esi's
    callback view runs, so its logging can safely slice it."""
    if getattr(esi.views.receive_callback, _PATCHED_ATTR, False):
        return

    original_receive_callback = esi.views.receive_callback

    def _safe_receive_callback(request, *args, **kwargs):
        if request.session.session_key is None:
            request.session.create()
        return original_receive_callback(request, *args, **kwargs)

    setattr(_safe_receive_callback, _PATCHED_ATTR, True)
    esi.views.receive_callback = _safe_receive_callback
