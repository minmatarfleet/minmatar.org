from django.test import SimpleTestCase

from app import contracts
from app.urls import api

SCHEMA = contracts.WEB.parent.parent / "src" / "types" / "generated"


class OpenApiSchemaTest(SimpleTestCase):
    """The website's API types are generated from this schema
    (frontend/app/src/types/generated/), so an endpoint change shows up as a
    type change there. After changing an endpoint, regenerate both:

        UPDATE_CONTRACTS=1 python manage.py test app.tests.test_openapi_schema
        cd ../frontend/app && npm run gen:api
    """

    def test_committed_schema_is_current(self):
        contracts.check(
            self, SCHEMA / "openapi.json", api.get_openapi_schema()
        )
