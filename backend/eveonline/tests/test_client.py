from django.test import SimpleTestCase

from eveonline.client import EsiResponse


class EsiClientTest(SimpleTestCase):
    """Test what we can of the EsiClient"""

    def test_response_error(self):
        response = EsiResponse(response_code=500, data="Boom!")

        self.assertRaises(ValueError, response.results)
