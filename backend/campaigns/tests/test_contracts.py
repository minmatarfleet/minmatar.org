"""Every endpoint must be able to say no without raising.

Ninja refuses to serialise a status that is not in the operation's response
map, so a denial path that was never declared answers 500 with a traceback
instead of the refusal it meant to send.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.endpoints.base import router
from campaigns.tests.helpers import auth_headers, make_campaign

BASE = "/api/campaigns"

# Bodies good enough to get past validation and reach the permission check.
SAMPLE_BODIES = {
    "/{slug}/enlist": {"source": "web"},
    "/{slug}/gangs": {"ships": "Rifters"},
    "/{slug}/systems/{system_id}/advantage": {
        "our_pct": 10.0,
        "enemy_pct": 5.0,
    },
    "": {
        "name": "Probe",
        "slug": "probe-campaign",
        "short_code": "PRB",
        "start_at": "2026-10-01T11:00:00Z",
        "end_at": "2026-11-01T11:00:00Z",
    },
    "/{slug}/commander-order": {"text": "hold the line"},
    "/{slug}/week/{target_id}": {"target": 1000.0, "accept": True},
}


class DenialContractTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()
        self.nobody = User.objects.create(username="nobody")

    def _paths(self):
        for path, operations in router.path_operations.items():
            for operation in operations.operations:
                for method in operation.methods:
                    yield method, path, operation

    def _url(self, path: str) -> str:
        return (
            f"{BASE}{path}".replace("{slug}", self.campaign.slug)
            .replace("{system_id}", str(self.system.id))
            .replace("{character_id}", "1")
            .replace("{target_id}", "1")
        )

    def test_no_endpoint_500s_when_it_refuses_an_unprivileged_caller(self):
        failures = []
        for method, path, _ in self._paths():
            url = self._url(path)
            body = SAMPLE_BODIES.get(path, {})
            response = self.client.generic(
                method,
                url,
                data=__import__("json").dumps(body) if body else "",
                content_type="application/json",
                **auth_headers(self.nobody),
            )
            if response.status_code >= 500:
                failures.append(f"{method} {path} -> {response.status_code}")

        self.assertEqual(failures, [], "; ".join(failures))

    def test_no_endpoint_500s_for_an_anonymous_caller(self):
        failures = []
        for method, path, _ in self._paths():
            url = self._url(path)
            body = SAMPLE_BODIES.get(path, {})
            response = self.client.generic(
                method,
                url,
                data=__import__("json").dumps(body) if body else "",
                content_type="application/json",
            )
            if response.status_code >= 500:
                failures.append(f"{method} {path} -> {response.status_code}")

        self.assertEqual(failures, [], "; ".join(failures))

    def test_every_write_declares_a_refusal_status(self):
        """A write that can only answer 200 cannot refuse anybody."""
        missing = []
        for method, path, operation in self._paths():
            if method in ("GET", "HEAD"):
                continue
            codes = set(operation.response_models or {})
            if not codes & {403, 404, 409, 400}:
                missing.append(f"{method} {path}")

        self.assertEqual(missing, [], "; ".join(missing))
