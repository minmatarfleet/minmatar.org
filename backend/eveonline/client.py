import logging
import requests
from typing import List

from django.conf import settings
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import (
    EveType,
    EveGroup,
    EveSolarSystem,
    EvePlanet,
    EveMoon,
    EveFaction,
    EveStation,
)

logger = logging.getLogger(__name__)

esi_provider = EsiClientProvider()

SUCCESS = 0
UNKNOWN_CLIENT_ERROR = 901
CHAR_ESI_SUSPENDED = 902
NO_CLIENT_CHAR = 903
NO_VALID_ACCESS_TOKEN = 904
NO_VALID_ESI_TOKEN = 905
ERROR_CALLING_ESI = 906

ESI_BASE_URL = "https://esi.evetech.net/latest"


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
        return self.response_code < 400

    def results(self):
        """Returns the data provided by the ESI call"""
        if self.success():
            return self.data
        else:
            raise ValueError(
                f"Cannot return data for failed ESI call ({self.response_code})"
            )

    def error_text(self):
        if self.success():
            return ""
        if self.response_code == 901:
            return f"Unknown ESI Client error ({self.response_code})"
        if self.response_code == 902:
            return f"ESI token suspended ({self.response_code})"
        if self.response_code == 903:
            return f"No character found ({self.response_code})"
        if self.response_code == 904:
            return f"No valid access token ({self.response_code})"
        if self.response_code == 905:
            return f"No valid ESI token ({self.response_code})"
        if self.response_code == 906:
            return f"Error calling ESI ({self.response_code})"
        if self.response_code < 500:
            return f"HTTP client error ({self.response_code})"
        if self.response_code < 600:
            return f"HTTP server error ({self.response_code})"

        return f"Unexpected ESI status ({self.response.code})"


class EsiClient:
    """
    An instance of the ESI client for a specific character

    Calls to the ESI API will use the token for that character. For
    public APIs you can use `EsiToken(None)`.
    """

    character_id: int
    character_esi_suspended: bool = False

    def __init__(self, character):
        if character is None:
            return
        elif isinstance(character, int):
            self.character_id = character
        elif hasattr(character, "character_id"):
            self.character_id = character.character_id
            self.character_esi_suspended = character.esi_suspended

    def _valid_token(self, required_scopes: List[str]) -> tuple[Token, int]:
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
        operation = esi_provider.client.Character.get_characters_character_id(
            character_id=char_id
        )
        return self._operation_results(operation)

    def get_character_skills(self) -> EsiResponse:
        """Returns the skills for the character this ESI client was created for."""

        token, status = self._valid_token(["esi-skills.read_skills.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = (
            esi_provider.client.Skills.get_characters_character_id_skills(
                character_id=self.character_id,
                token=token,
            )
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

        token, status = self._valid_token(["esi-assets.read_assets.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = (
            esi_provider.client.Assets.get_characters_character_id_assets(
                character_id=self.character_id,
                token=token,
            )
        )
        try:
            return EsiResponse(
                data=operation.results(),
                response_code=SUCCESS,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_recent_killmails(self) -> EsiResponse:
        """Returns a character's recent killmails"""

        token, status = self._valid_token(["esi-killmails.read_killmails.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Killmails.get_characters_character_id_killmails_recent(
            character_id=self.character_id,
            token=token,
        )

        return self._operation_results(operation)

    def get_character_killmail(
        self, killmail_id, killmail_hash
    ) -> EsiResponse:
        """Returns a character's killmail"""
        operation = esi_provider.client.Killmails.get_killmails_killmail_id_killmail_hash(
            killmail_id=killmail_id, killmail_hash=killmail_hash
        )
        return self._operation_results(operation)

    def get_character_contracts(self) -> EsiResponse:
        """Returns the contracts for the character this ESI client was created for"""

        token, status = self._valid_token(
            ["esi-contracts.read_character_contracts.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Contracts.get_characters_character_id_contracts(
            character_id=self.character_id,
            token=token,
        )
        return self._operation_results(operation)

    def get_corporation_contracts(self, corporation_id) -> EsiResponse:
        token, status = self._valid_token(
            ["esi-contracts.read_corporation_contracts.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Contracts.get_corporations_corporation_id_contracts(
            corporation_id=corporation_id,
            token=token,
        )

        return self._operation_results(operation)

    def get_public_contracts(self, region_id) -> EsiResponse:
        operation = (
            esi_provider.client.Contracts.get_contracts_public_region_id(
                region_id=region_id,
            )
        )

        return self._operation_results(operation)

    def get_active_fleet(self) -> EsiResponse:
        token, status = self._valid_token(["esi-fleets.read_fleet.v1"])
        if status > 0:
            return EsiResponse(status)

        response = requests.get(
            url=f"{ESI_BASE_URL}/characters/{self.character_id}/fleet/",
            timeout=10,
            headers={"Authorization": "Bearer " + token},
        )

        return EsiResponse(
            response_code=response.status_code, data=response.json()
        )

    def get_fleet_members(self, fleet_id: int) -> EsiResponse:
        token, status = self._valid_token(["esi-fleets.read_fleet.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.get_fleets_fleet_id_members(
            fleet_id=fleet_id, token=token
        )

        return self._operation_results(operation)

    def get_alliance(self, alliance_id: int) -> EsiResponse:
        operation = esi_provider.client.Alliance.get_alliances_alliance_id(
            alliance_id=alliance_id
        )
        return self._operation_results(operation)

    def get_corporation(self, corporation_id: int) -> EsiResponse:
        operation = (
            esi_provider.client.Corporation.get_corporations_corporation_id(
                corporation_id=corporation_id
            )
        )
        return self._operation_results(operation)

    def get_corporation_members(self, corporation_id: int) -> EsiResponse:
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Corporation.get_corporations_corporation_id_members(
            corporation_id=corporation_id,
            token=token,
        )

        return self._operation_results(operation)

    def send_evemail(self, mail_details) -> EsiResponse:
        required_scopes = ["esi-mail.send_mail.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Mail.post_characters_character_id_mail(
            mail=mail_details,
            character_id=self.character_id,
            token=token,
        )

        return self._operation_results(operation)

    def resolve_universe_names(self, ids_to_resolve) -> EsiResponse:
        operation = esi_provider.client.Universe.post_universe_names(
            ids=ids_to_resolve
        )
        return self._operation_results(operation)

    def get_fleet(self, fleet_id) -> EsiResponse:
        required_scopes = ["esi-fleets.read_fleet.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.get_fleets_fleet_id(
            fleet_id=fleet_id,
            token=token,
        )

        return self._operation_results(operation)

    def update_fleet_details(self, fleet_id, update) -> EsiResponse:
        required_scopes = ["esi-fleets.write_fleet.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.put_fleets_fleet_id(
            fleet_id=fleet_id,
            new_settings=update,
            token=token,
        )

        return self._operation_results(operation)

    def get_character_notifications(self) -> EsiResponse:
        """Returns recent notifications for the character"""

        token, status = self._valid_token(
            ["esi-characters.read_notifications.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        # Use direct call as Swagger validation fails
        response = requests.get(
            url=f"{ESI_BASE_URL}/characters/{self.character_id}/notifications/",
            timeout=10,
            headers={"Authorization": "Bearer " + token},
        )

        if response.status_code == 200:
            return EsiResponse(response_code=200, data=response.json())
        else:
            return EsiResponse(
                response_code=response.status_code,
                data=response.text,
            )

    def get_character_affiliations(self, character_ids) -> EsiResponse:
        """
        Returns the affiliations for a batch of characters.
        """
        operation = esi_provider.client.Character.post_characters_affiliation(
            characters=character_ids
        )
        return self._operation_results(operation)

    def get_corp_structures(self, corp_id: int) -> EsiResponse:
        """
        Returns all the structures owned by a corp
        """
        token, status = self._valid_token(
            ["esi-corporations.read_structures.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Corporation.get_corporations_corporation_id_structures(
            corporation_id=corp_id,
            token=token,
        )

        return self._operation_results(operation)

    def get_eve_type(self, type_id, include_children: bool = False):
        """
        Returns the item with the specified type ID.

        A copy of the item will be cached in the database.
        """
        value, _ = EveType.objects.get_or_create_esi(
            id=type_id,
            include_children=include_children,
        )
        return value

    def get_eve_group(self, group_id, include_children: bool = False):
        """
        Returns the eve group with the specified ID.

        A copy of the data will be cached in the database.
        """
        eve_group, _ = EveGroup.objects.get_or_create_esi(
            id=group_id,
            include_children=include_children,
        )
        return eve_group

    def get_faction(self, faction_id):
        """
        Returns the faction with the specified ID.

        A copy of the data will be cached in the database.
        """
        value, _ = EveFaction.objects.get_or_create_esi(id=faction_id)
        return value

    def get_solar_system(self, system_id):
        """
        Returns the solar system with the specified ID.

        A copy of the system will be cached in the database.
        """
        value, _ = EveSolarSystem.objects.get_or_create_esi(id=system_id)
        return value

    def get_planet(self, planet_id):
        """
        Returns the planet with the specified ID.

        A copy of the system will be cached in the database.
        """
        value, _ = EvePlanet.objects.get_or_create_esi(id=planet_id)
        return value

    def get_moon(self, moon_id):
        """
        Returns the moon with the specified ID.

        A copy of the system will be cached in the database.
        """
        value, _ = EveMoon.objects.get_or_create_esi(id=moon_id)
        return value

    def get_station(self, station_id):
        """
        Returns the station with the specified ID.

        A copy of the data will be cached in the database.
        """
        station, _ = EveStation.objects.get_or_create_esi(
            id=station_id,
        )
        return station


def esi_for(character) -> EsiClient:
    """
    Returns an ESI client for the specified character.

    The saved auth token for the character will be used.

    The client might be a mock if configured for mocking in settings.py
    """
    if hasattr(settings, "MOCK_ESI") and settings.MOCK_ESI:
        # pylint: disable=import-outside-toplevel
        # Import locally to avoid circular dependency
        from eveonline.mock_esi.esi_mock import (
            get_mock_esi,
        )

        return get_mock_esi(character)
    else:
        return EsiClient(character)


def esi_public() -> EsiClient:
    """
    Returns an ESI client for accessing public ESI endpoints.

    The saved auth token for the character will be used.

    The client might be a mock if configured for mocking in settings.py
    """

    return esi_for(None)
