from unittest.mock import patch

from app.test import TestCase

from eveonline.client import EsiResponse

from eveonline.tasks import update_character_assets, update_character_skills
from eveonline.models import EveCharacter


class EveOnlineTaskTests(TestCase):
    """
    Tests methods of the EveOnline tasks.
    """

    def test_update_character_asset_task(self):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        with patch("eveonline.tasks.EsiClient") as esi_mock:
            instance = esi_mock.return_value
            instance.get_character_assets.return_value = EsiResponse(
                response_code=200, data=[]
            )

            #  No data returned by ESI, so won't actually test creating assets

            update_character_assets(char.id)

    def test_update_character_skills(self):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        with patch("eveonline.helpers.skills.EsiClient") as esi_mock:
            instance = esi_mock.return_value
            instance.get_character_skills.return_value = EsiResponse(
                response_code=200,
                data=[],
            )

            update_character_skills(char.id)
