"""A transport-agnostic fake for raw ESI HTTP in tests.

Patches ``requests.Session.send``, which both ``requests.get`` and
``requests.request`` end in, so a test sees the same requests whichever
helper the code under test uses.
"""

from __future__ import annotations

import json
from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

import requests
from requests.structures import CaseInsensitiveDict


def make_response(status=200, body=None, headers=None, raw_text=None):
    response = requests.Response()
    response.status_code = status
    if raw_text is not None:
        response._content = raw_text.encode()  # pylint: disable=W0212
    elif body is None:
        response._content = b""  # pylint: disable=W0212
    else:
        response._content = json.dumps(body).encode()  # pylint: disable=W0212
    response.headers = CaseInsensitiveDict(headers or {})
    response.encoding = "utf-8"
    return response


class FakeEsi:
    """Route table keyed by (METHOD, path, page) -> response or exception.

    ``path`` is the URL path without the ``/latest`` prefix. ``page`` is
    the ``page`` query value as a string, or None when absent.
    """

    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, method, path, response, page=None):
        self.routes[(method.upper(), path, page)] = response
        return self

    def _send(self, prepared):
        parts = urlsplit(prepared.url)
        path = parts.path
        if path.startswith("/latest"):
            path = path[len("/latest") :]
        query = dict(parse_qsl(parts.query))
        self.calls.append(
            {
                "method": prepared.method,
                "url": prepared.url.split("?")[0],
                "path": path,
                "query": query,
                "headers": dict(prepared.headers),
                "body": prepared.body,
            }
        )
        key = (prepared.method, path, query.get("page"))
        if key not in self.routes:
            key = (prepared.method, path, None)
        response = self.routes.get(key)
        if response is None:
            raise AssertionError(f"Unexpected ESI call {key} {query}")
        if isinstance(response, Exception):
            raise response
        response.url = prepared.url
        response.request = prepared
        return response

    def requested(self):
        """(method, path, sorted query) for each call, in order."""
        return [
            (c["method"], c["path"], tuple(sorted(c["query"].items())))
            for c in self.calls
        ]

    def handle(self, prepared):
        """Answer one prepared request from the route table."""
        return self._send(prepared)

    def install(self, testcase):
        """Patch requests for the rest of ``testcase``."""
        fake = self

        def send(session, prepared, **kwargs):
            del session, kwargs
            return fake.handle(prepared)

        patcher = patch.object(requests.Session, "send", send)
        patcher.start()
        testcase.addCleanup(patcher.stop)
        return self
