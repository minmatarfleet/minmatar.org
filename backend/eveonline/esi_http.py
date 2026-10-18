"""One transport for ESI routes we call without the django-esi client.

django-esi's OpenAPI operations already send a User-Agent and the
compatibility date, and handle ESI's error limit. The routes we call with
``requests`` instead (paginated corporation reads, planets, clones,
notifications, fittings, corporation projects, killmails by hash) go through
``esi_request`` so every one of them:

- identifies the app with the same User-Agent django-esi sends,
- reports its status to the app-wide error budget (``esi_budget``),
- uses one timeout and one exception policy,
- follows ``X-Pages`` when asked, one page at a time (no concurrency).

``compat=True`` adds ``X-Compatibility-Date``. Routes that never sent it keep
``compat=False`` for now: switching a ``/latest`` route to a compatibility
date can rename fields, so that is done one route at a time.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from typing import Any

import requests
from requests.structures import CaseInsensitiveDict

from eveonline import esi_budget

logger = logging.getLogger(__name__)

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_COMPATIBILITY_DATE = "2026-06-09"
DEFAULT_TIMEOUT_SECONDS = 30
UA_APPNAME = "MinmatarOrg"
UA_VERSION = "1.0.0"
UA_URL = "https://minmatar.org"
# A runaway X-Pages header must not turn one call into thousands.
MAX_PAGES = 500


@functools.lru_cache(maxsize=1)
def user_agent() -> str:
    """The User-Agent django-esi sends, so ESI sees one application."""
    try:
        # pylint: disable=import-outside-toplevel
        from esi.openapi_clients import _build_user_agent

        return _build_user_agent(UA_APPNAME, UA_VERSION, UA_URL)
    except Exception:  # pragma: no cover - django-esi internals moved
        return f"{UA_APPNAME}/{UA_VERSION} (+{UA_URL})"


@dataclass
class EsiHttpResult:
    """What one ``esi_request`` produced.

    ``status`` is the HTTP status of the last response, or None when the
    request raised (``error`` holds the exception). ``data`` is the decoded
    JSON body: every page concatenated for a paged call, and the error body
    (when it is JSON) for a 4xx/5xx.
    """

    status: int | None
    data: Any = None
    text: str = ""
    headers: CaseInsensitiveDict = field(default_factory=CaseInsensitiveDict)
    response: requests.Response | None = None
    error: Exception | None = None
    pages: int = 0

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.status is not None
            and (self.status < 400)
        )


def esi_url(path: str) -> str:
    """Absolute ESI URL for ``/characters/...`` or an already-full URL."""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{ESI_BASE_URL}{path}"


def esi_headers(
    access_token: str | None = None, *, compat: bool = False, extra=None
) -> dict:
    headers = {"User-Agent": user_agent(), "Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if compat:
        headers["X-Compatibility-Date"] = ESI_COMPATIBILITY_DATE
    if extra:
        headers.update(extra)
    return headers


def _decode(response: requests.Response, empty):
    if not response.content:
        return empty
    return response.json()


def _send(
    *, method, url, headers, params, json_body, timeout, account
):  # pylint: disable=too-many-arguments
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    if account:
        esi_budget.observe_response(
            response.status_code, CaseInsensitiveDict(response.headers or {})
        )
    return response


def esi_request(
    method: str,
    path: str,
    *,
    access_token: str | None = None,
    params: dict | None = None,
    json_body=None,
    headers: dict | None = None,
    paged: bool = False,
    compat: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    account: bool = True,
    empty=None,
) -> EsiHttpResult:
    """Call one ESI route and decode the JSON body.

    ``paged=True`` asks for page 1, then every page up to ``X-Pages``, and
    concatenates the lists. Any failing page fails the whole call, as the
    per-method loops did. ``empty`` is the value for a body-less success.
    ``account=False`` is for callers that account the response themselves
    with a token bucket (``esi_budget.note_call``), so nothing counts twice.
    """
    request = {
        "method": method,
        "url": esi_url(path),
        "headers": esi_headers(access_token, compat=compat, extra=headers),
        "json_body": json_body,
        "timeout": timeout,
        "account": account,
    }
    base_params = dict(params or {})
    if paged:
        base_params["page"] = 1
        if empty is None:
            empty = []

    result = _fetch(request, base_params or None, empty)
    if not result.ok or not paged:
        return result

    try:
        total_pages = int(result.headers.get("X-Pages", 1) or 1)
    except (TypeError, ValueError):
        total_pages = 1
    total_pages = min(total_pages, MAX_PAGES)
    rows = list(result.data or [])
    for page in range(2, total_pages + 1):
        page_result = _fetch(request, {**base_params, "page": page}, [])
        if not page_result.ok:
            page_result.pages = page - 1
            return page_result
        rows.extend(page_result.data or [])
    result.data = rows
    result.pages = total_pages
    return result


def _fetch(request: dict, params, empty) -> EsiHttpResult:
    """One HTTP call. A raised request becomes ``status=None``."""
    try:
        response = _send(**request, params=params)
    except Exception as e:  # network, DNS, timeout
        logger.warning(
            "ESI %s %s raised: %s", request["method"], request["url"], e
        )
        if request["account"]:
            esi_budget.record_error()
        return EsiHttpResult(status=None, error=e)
    return _result(response, empty)


def _result(response: requests.Response, empty) -> EsiHttpResult:
    headers = CaseInsensitiveDict(response.headers or {})
    status = response.status_code
    if status >= 400:
        try:
            data = response.json() if response.content else None
        except ValueError:
            data = None
        return EsiHttpResult(
            status=status,
            data=data,
            text=response.text,
            headers=headers,
            response=response,
        )
    try:
        data = _decode(response, empty)
    except ValueError as e:
        return EsiHttpResult(
            status=status,
            text=response.text,
            headers=headers,
            response=response,
            error=e,
        )
    return EsiHttpResult(
        status=status,
        data=data,
        headers=headers,
        response=response,
        pages=1,
    )
