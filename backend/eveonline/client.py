from typing import List
import esi
from esi.models import Token

from .models import EveCharacter


class EsiResponse:
    """Represents a response from the ESI API"""

    data: any
    response: any
    response_code: int

    def success(self):
        """Returns true of the ESI call was successful."""
        return self.response_code <= 400

    def results(self):
        """Returns the data provided by the ESI call"""
        if self.success():
            return self.data
        else:
            raise ValueError("Cannot return data for failed ESI call")


class EsiClient:
    """An instance of the ESI client for a specific character"""

    character_id: int

    def get_valid_token(self, required_scopes: List[str]) -> Token:
        if not self.character_id:
            return False

        token = Token.get_token(self.character_id, required_scopes)
        if not token:
            return False

        try:
            return token.valid_access_token()
        except Exception:
            return False

    def get_character_skills(self) -> EsiResponse:
        """Returns the skills for the character this ESI client was created for."""
        token = self.get_valid_token(["esi-skills.read_skills.v1"])
        if not token:
            return EsiResponse(data=None, response=None, response_code=999)

        operation = esi.client.Skills.get_characters_character_id_skills(
            character_id=self.character_id,
            token=token,
        )
        operation.request_config.also_return_response = True
        data, response = operation.results()
        return EsiResponse(
            data=data["skills"], response=response, response_code=200
        )


def esi_client(character: EveCharacter | int) -> EsiClient:
    """Return an ESI client instance for a particular Eve character."""
    if isinstance(character, int):
        return EsiClient(character_id=character)
    elif isinstance(character, EveCharacter):
        return EsiClient(character_id=character.character_id)
    else:
        raise ValueError("No valid character provided for EsiClient")
