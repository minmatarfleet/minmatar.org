import logging

from typing import List
from esi.clients import EsiClientProvider
from esi.models import Token
from eveonline.scopes import MARKET_CHARACTER_SCOPES, BASIC_SCOPES

from .models import EveCharacter

logger = logging.getLogger(__name__)

esi = EsiClientProvider()

SUCCESS = 0
UNKNOWN_CLIENT_ERROR = 901
CHAR_ESI_SUSPENDED = 902
NO_CLIENT_CHAR = 903
NO_VALID_ACCESS_TOKEN = 904
NO_VALID_ESI_TOKEN = 905
ERROR_CALLING_ESI = 906


class EsiResponse:
    """Represents a response from the ESI API"""

    data: any
    response: any
    response_code: int

    def __init__(self, response_code, data=None, response=None):
        self.data = data
        self.response = response
        self.response_code = response_code

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
    character_esi_suspended: bool = False

    def __init__(self, character: int | EveCharacter | None):
        if character is None:
            return
        elif isinstance(character, int):
            self.character_id = character
        elif isinstance(character, EveCharacter):
            self.character_id = character.character_id
            self.character_esi_suspended = character.esi_suspended

    def get_valid_token(self, required_scopes: List[str]) -> tuple[Token, int]:
        if not self.character_id:
            return None, NO_CLIENT_CHAR

        if self.character_esi_suspended:
            return None, CHAR_ESI_SUSPENDED

        token = Token.get_token(self.character_id, required_scopes)
        if not token:
            return None, NO_VALID_ESI_TOKEN

        try:
            return token.valid_access_token(), SUCCESS
        except Exception:
            return None, NO_VALID_ACCESS_TOKEN

    def _operation_results(self, operation) -> EsiResponse:
        try:
            return EsiResponse(response_code=SUCCESS, data=operation.results())
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_character_public_data(self, char_id: int) -> EsiResponse:
        """Returns the public data for the specified Eve character."""
        operation = esi.client.Character.get_characters_character_id(
            character_id=char_id
        )
        return self._operation_results(operation)

    def get_character_skills(self) -> EsiResponse:
        """Returns the skills for the character this ESI client was created for."""

        token, status = self.get_valid_token(["esi-skills.read_skills.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi.client.Skills.get_characters_character_id_skills(
            character_id=self.character_id,
            token=token,
        )

        try:
            data = operation.results()
            return EsiResponse(
                data=data["skills"] if data else None,
                response_code=SUCCESS,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_character_assets(self) -> EsiResponse:
        """Returns the assets of the character this ESI client was created for."""

        token, status = self.get_valid_token(["esi-assets.read_assets.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi.client.Assets.get_characters_character_id_assets(
            character_id=self.character_id,
            token=token,
        )
        try:
            return EsiResponse(
                data=operation.results(),
                response_code=SUCCESS,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_character_contracts(self) -> EsiResponse:
        """Returns the contracts for the character this ESI client was created for"""

        token, status = self.get_valid_token(MARKET_CHARACTER_SCOPES)
        if status > 0:
            return EsiResponse(status)

        operation = esi.client.Contracts.get_characters_character_id_contracts(
            character_id=self.character_id,
            token=token,
        )
        return self._operation_results(operation)

    def get_active_fleet(self) -> EsiResponse:
        token, status = self.get_valid_token(BASIC_SCOPES)
        if status > 0:
            return EsiResponse(status)

        operation = esi.client.Fleets.get_characters_character_id_fleet(
            character_id=self.character_id,
            token=token,
        )
        return self._operation_results(operation)
