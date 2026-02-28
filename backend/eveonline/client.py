import logging
import requests
from typing import List

from django.conf import settings
from esi.clients import EsiClientProvider
from esi.errors import TokenInvalidError
from esi.models import Token
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
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

        return f"Unexpected ESI status ({self.response_code})"


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
        except (InvalidGrantError, TokenInvalidError):
            # Import here to avoid circular import (eveonline.models loads client)
            from eveonline.models import (  # pylint: disable=import-outside-toplevel
                EveCharacter,
            )

            EveCharacter.objects.filter(character_id=self.character_id).update(
                esi_suspended=True
            )
            logger.info(
                "Set esi_suspended=True for character %s (invalid/expired refresh token)",
                self.character_id,
            )
            return None, NO_VALID_ACCESS_TOKEN
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

    def get_character_blueprints(self) -> EsiResponse:
        """
        Returns all blueprints for the character. Paginated; fetches all pages.
        Requires esi-characters.read_blueprints.v1.
        """
        token, status = self._valid_token(
            ["esi-characters.read_blueprints.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        url = f"{ESI_BASE_URL}/characters/{self.character_id}/blueprints/"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.get(
                url,
                params={"page": 1},
                headers=headers,
                timeout=30,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        if resp.status_code >= 400:
            return EsiResponse(response_code=resp.status_code)

        all_blueprints = resp.json() if resp.content else []
        total_pages = int(resp.headers.get("X-Pages", 1))

        for page in range(2, total_pages + 1):
            try:
                page_resp = requests.get(
                    url,
                    params={"page": page},
                    headers=headers,
                    timeout=30,
                )
            except Exception as e:
                return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
            if page_resp.status_code >= 400:
                return EsiResponse(response_code=page_resp.status_code)
            page_data = page_resp.json() if page_resp.content else []
            all_blueprints.extend(page_data)

        return EsiResponse(response_code=SUCCESS, data=all_blueprints)

    def get_character_industry_jobs(
        self, include_completed: bool = True
    ) -> EsiResponse:
        """
        Returns industry jobs for the character.
        ESI does not support pagination for this endpoint; all jobs are returned in one response.
        Requires esi-industry.read_character_jobs.v1.
        """
        token, status = self._valid_token(
            ["esi-industry.read_character_jobs.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Industry.get_characters_character_id_industry_jobs(
            character_id=self.character_id,
            token=token,
            include_completed=include_completed,
        )
        try:
            jobs = operation.results()
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        return EsiResponse(response_code=SUCCESS, data=jobs or [])

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

    def get_corporation_blueprints(self, corporation_id: int) -> EsiResponse:
        """
        Returns all blueprints for the corporation. Paginated; fetches all pages.
        Requires esi-corporations.read_blueprints.v1 (Director).
        """
        token, status = self._valid_token(
            ["esi-corporations.read_blueprints.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        url = f"{ESI_BASE_URL}/corporations/{corporation_id}/blueprints/"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.get(
                url,
                params={"page": 1},
                headers=headers,
                timeout=30,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        if resp.status_code >= 400:
            return EsiResponse(response_code=resp.status_code)

        all_blueprints = resp.json() if resp.content else []
        total_pages = int(resp.headers.get("X-Pages", 1))

        for page in range(2, total_pages + 1):
            try:
                page_resp = requests.get(
                    url,
                    params={"page": page},
                    headers=headers,
                    timeout=30,
                )
            except Exception as e:
                return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
            if page_resp.status_code >= 400:
                return EsiResponse(response_code=page_resp.status_code)
            page_data = page_resp.json() if page_resp.content else []
            all_blueprints.extend(page_data)

        return EsiResponse(response_code=SUCCESS, data=all_blueprints)

    def get_corporation_industry_jobs(
        self, corporation_id: int, include_completed: bool = True
    ) -> EsiResponse:
        """
        Returns industry jobs for the corporation. Paginated; fetches all pages.
        Requires esi-industry.read_corporation_jobs.v1 (e.g. Factory_Manager).
        """
        token, status = self._valid_token(
            ["esi-industry.read_corporation_jobs.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        url = f"{ESI_BASE_URL}/corporations/{corporation_id}/industry/jobs/"
        params = {"include_completed": include_completed}
        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.get(
                url,
                params={**params, "page": 1},
                headers=headers,
                timeout=30,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        if resp.status_code >= 400:
            return EsiResponse(response_code=resp.status_code)

        all_jobs = resp.json() if resp.content else []
        total_pages = int(resp.headers.get("X-Pages", 1))

        for page in range(2, total_pages + 1):
            try:
                page_resp = requests.get(
                    url,
                    params={**params, "page": page},
                    headers=headers,
                    timeout=30,
                )
            except Exception as e:
                return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
            if page_resp.status_code >= 400:
                return EsiResponse(response_code=page_resp.status_code)
            page_jobs = page_resp.json() if page_resp.content else []
            all_jobs.extend(page_jobs)

        return EsiResponse(response_code=SUCCESS, data=all_jobs)

    def get_corporation_wallet_journal(
        self, corporation_id: int, division: int, page: int = 1
    ) -> EsiResponse:
        """
        Returns wallet journal for one corporation division and page.
        Requires esi-wallet.read_corporation_wallets.v1 (Director/Market/Accountant).
        """
        token, status = self._valid_token(
            ["esi-wallet.read_corporation_wallets.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        url = f"{ESI_BASE_URL}/corporations/{corporation_id}/wallets/{division}/journal/"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.get(
                url,
                params={"page": page},
                headers=headers,
                timeout=30,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        if resp.status_code >= 400:
            return EsiResponse(response_code=resp.status_code)

        data = resp.json() if resp.content else []
        return EsiResponse(response_code=SUCCESS, data=data)

    def get_corporation_wallet_journal_all_divisions(
        self, corporation_id: int
    ) -> EsiResponse:
        """
        Fetches all wallet journal entries for all divisions (1-7), all pages.
        Requires esi-wallet.read_corporation_wallets.v1.
        Returns EsiResponse with data = list of (division, entries) or flat list.
        """
        token, status = self._valid_token(
            ["esi-wallet.read_corporation_wallets.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        all_entries = []
        for division in range(1, 8):
            page = 1
            while True:
                url = f"{ESI_BASE_URL}/corporations/{corporation_id}/wallets/{division}/journal/"
                headers = {"Authorization": f"Bearer {token}"}
                try:
                    resp = requests.get(
                        url,
                        params={"page": page},
                        headers=headers,
                        timeout=30,
                    )
                except Exception as e:
                    return EsiResponse(
                        response_code=ERROR_CALLING_ESI, response=e
                    )
                if resp.status_code >= 400:
                    return EsiResponse(response_code=resp.status_code)
                entries = resp.json() if resp.content else []
                for e in entries:
                    e["division"] = division
                all_entries.extend(entries)
                total_pages = int(resp.headers.get("X-Pages", 1))
                if page >= total_pages:
                    break
                page += 1

        return EsiResponse(response_code=SUCCESS, data=all_entries)

    def get_public_contracts(self, region_id) -> EsiResponse:
        operation = (
            esi_provider.client.Contracts.get_contracts_public_region_id(
                region_id=region_id,
            )
        )

        return self._operation_results(operation)

    def get_region_market_history(
        self, region_id: int, type_id: int
    ) -> EsiResponse:
        """
        Fetch daily market history for a type in a region (public endpoint).
        Returns list of dicts with date, average, highest, lowest, order_count, volume.
        """
        url = f"{ESI_BASE_URL}/markets/{region_id}/history/"
        try:
            resp = requests.get(
                url,
                params={"type_id": type_id},
                timeout=30,
            )
        except Exception as e:
            logger.exception(
                "ESI request failed for region %s type %s: %s",
                region_id,
                type_id,
                e,
            )
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        if resp.status_code >= 400:
            return EsiResponse(response_code=resp.status_code)
        data = resp.json() if resp.content else []
        return EsiResponse(response_code=SUCCESS, data=data)

    def get_structure_market_orders(self, structure_id: int) -> EsiResponse:
        """
        Returns all market orders in a structure (requires character with
        esi-markets.structure_markets.v1 and docking access to the structure).
        Paginates automatically and returns the full list.
        Prefer get_structure_market_orders_pages() for large structures to avoid OOM.
        """
        all_orders = []
        for page_data in self.get_structure_market_orders_pages(structure_id):
            if page_data is None:
                return EsiResponse(response_code=NO_VALID_ESI_TOKEN)
            all_orders.extend(page_data)
        return EsiResponse(response_code=SUCCESS, data=all_orders)

    def get_structure_market_orders_first_page_and_total(
        self, structure_id: int
    ) -> tuple[list | None, int]:
        """
        Fetch page 1 of structure market orders and return (data, total_pages).
        Uses a single request so we can read the X-Pages header. Returns
        (None, 0) if token invalid or request fails.
        """
        token, status = self._valid_token(["esi-markets.structure_markets.v1"])
        if status > 0:
            return None, 0

        url = f"{ESI_BASE_URL}/markets/structures/{structure_id}/"
        try:
            resp = requests.get(
                url,
                params={"page": 1},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
        except Exception as e:
            logger.exception(
                "ESI request failed for structure %s: %s", structure_id, e
            )
            return None, 0

        if resp.status_code >= 400:
            return None, 0

        total_pages = int(resp.headers.get("X-Pages", 1))
        data = resp.json() if resp.content else []
        return data, total_pages

    def get_structure_market_orders_page(
        self, structure_id: int, page: int
    ) -> EsiResponse:
        """
        Fetch a single page of structure market orders (1-based page number).
        """
        token, status = self._valid_token(["esi-markets.structure_markets.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = (
            esi_provider.client.Market.get_markets_structures_structure_id(
                structure_id=structure_id,
                page=page,
                token=token,
            )
        )
        try:
            page_data = operation.results()
            return EsiResponse(response_code=SUCCESS, data=page_data)
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_structure_market_orders_pages(self, structure_id: int):
        """
        Yields one page of market orders at a time (requires character with
        esi-markets.structure_markets.v1 and docking access). Use this for
        large structures to avoid loading all orders into memory. Yields None
        once if token is invalid.
        """
        token, status = self._valid_token(["esi-markets.structure_markets.v1"])
        if status > 0:
            yield None
            return

        page = 1
        page_size = 1000
        while True:
            operation = (
                esi_provider.client.Market.get_markets_structures_structure_id(
                    structure_id=structure_id,
                    page=page,
                    token=token,
                )
            )
            page_data = operation.results()
            if not page_data:
                break
            yield page_data
            if len(page_data) < page_size:
                break
            page += 1

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

    def get_alliance_corporations(self, alliance_id: int) -> EsiResponse:
        operation = esi_provider.client.Alliance.get_alliances_alliance_id_corporations(
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

    def get_corporation_roles(self, corporation_id: int) -> EsiResponse:
        """Returns roles of all corporation members. Requires Personnel_Manager or grantable role."""
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Corporation.get_corporations_corporation_id_roles(
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

    def get_character_planets(self) -> EsiResponse:
        """Returns the list of planetary colonies for the character."""
        token, status = self._valid_token(["esi-planets.manage_planets.v1"])
        if status > 0:
            return EsiResponse(status)

        response = requests.get(
            url=f"{ESI_BASE_URL}/characters/{self.character_id}/planets/",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            return EsiResponse(response_code=SUCCESS, data=response.json())
        return EsiResponse(response_code=response.status_code)

    def get_character_planet_details(self, planet_id: int) -> EsiResponse:
        """Returns the full layout (pins, routes, links) for a character's planet colony."""
        token, status = self._valid_token(["esi-planets.manage_planets.v1"])
        if status > 0:
            return EsiResponse(status)

        response = requests.get(
            url=f"{ESI_BASE_URL}/characters/{self.character_id}/planets/{planet_id}/",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            return EsiResponse(response_code=SUCCESS, data=response.json())
        return EsiResponse(response_code=response.status_code)

    def get_universe_schematic(self, schematic_id: int) -> EsiResponse:
        """
        Returns PI schematic info (cycle_time, schematic_name).

        Public endpoint; no auth required. Cached by ESI for up to 3600 seconds.
        """
        response = requests.get(
            url=f"{ESI_BASE_URL}/universe/schematics/{schematic_id}/",
            timeout=30,
        )
        if response.status_code == 200:
            return EsiResponse(response_code=SUCCESS, data=response.json())
        return EsiResponse(response_code=response.status_code)

    def get_character_mining_ledger(self) -> EsiResponse:
        """Returns the personal mining ledger for the character (last 30 days)."""
        token, status = self._valid_token(
            ["esi-industry.read_character_mining.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        response = requests.get(
            url=f"{ESI_BASE_URL}/characters/{self.character_id}/mining/",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            return EsiResponse(response_code=SUCCESS, data=response.json())
        return EsiResponse(response_code=response.status_code)

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


def get_region_market_orders_pages(region_id: int, type_id: int | None = None):
    """
    Yields one page of market orders at a time for a region (public endpoint,
    no auth). Each order includes location_id, type_id, price, is_buy_order,
    range, etc. Use this for NPC station locations; filter by location_id.
    If type_id is set, only orders for that type are returned (fewer pages).
    """
    page = 1
    page_size = 1000
    params: dict = {"page": page}
    if type_id is not None:
        params["type_id"] = type_id
    while True:
        url = f"{ESI_BASE_URL}/markets/{region_id}/orders/"
        try:
            resp = requests.get(url, params=params, timeout=30)
        except Exception as e:
            logger.exception(
                "ESI request failed for region %s page %s: %s",
                region_id,
                page,
                e,
            )
            yield None
            return
        if resp.status_code >= 400:
            yield None
            return
        page_data = resp.json() if resp.content else []
        if not page_data:
            break
        yield page_data
        if len(page_data) < page_size:
            break
        page += 1
        params["page"] = page


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
