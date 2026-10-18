import logging
from typing import Any, List

from django.conf import settings

from app.dev_switches import mock_esi_enabled
from esi.errors import TokenInvalidError
from esi.exceptions import ESIErrorLimitException, HTTPClientError
from esi.models import Token
from esi.openapi_clients import ESIClientProvider
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from eveonline import esi_budget
from eveonline.esi_http import (  # noqa: F401 - re-exported constants
    ESI_BASE_URL,
    ESI_COMPATIBILITY_DATE,
    EsiHttpResult,
    esi_request,
)
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

SUCCESS = 0
UNKNOWN_CLIENT_ERROR = 901
CHAR_ESI_SUSPENDED = 902
NO_CLIENT_CHAR = 903
NO_VALID_ACCESS_TOKEN = 904
NO_VALID_ESI_TOKEN = 905
ERROR_CALLING_ESI = 906

SCOPE_CORPORATION_PROJECTS = ["esi-corporations.read_projects.v1"]
# Cursor routes return at most 100 rows a page; stop a runaway walk.
MAX_CURSOR_PAGES = 50


def live_esi_allowed() -> bool:
    """
    Whether live ESI HTTP is permitted.

    settings_test sets TESTING=True and ALLOW_LIVE_ESI_IN_TESTS=False.
    Opt in only for intentional live runs or tests that mock the ESI
    provider and need the real call path.
    """
    if not getattr(settings, "TESTING", False):
        return True
    return bool(getattr(settings, "ALLOW_LIVE_ESI_IN_TESTS", False))


def assert_esi_http_allowed() -> None:
    """
    Block live ESI HTTP during Django unit tests unless explicitly enabled.

    Prefer seeding local rows or passing mock payloads (e.g. offers=).
    """
    if live_esi_allowed():
        return
    raise RuntimeError(
        "Refusing live ESI HTTP during unit tests. Seed local data, "
        "pass mock payloads, patch the caller, or set "
        "ALLOW_LIVE_ESI_IN_TESTS=True only for intentional live runs."
    )


esi_provider = ESIClientProvider(
    compatibility_date=ESI_COMPATIBILITY_DATE,
    ua_appname="MinmatarOrg",
    ua_version="1.0.0",
    ua_url="https://minmatar.org",
    tags=[
        "Alliance",
        "Assets",
        "Character",
        "Contracts",
        "Corporation",
        "Faction Warfare",
        "Fleets",
        "Industry",
        "Killmails",
        "Mail",
        "Market",
        "Loyalty",
        "Skills",
        "Universe",
    ],
)


def _esi_to_python(data: Any) -> Any:
    """Normalize OpenAPI/Pydantic responses to plain dict/list for callers."""
    if data is None:
        return None
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    if isinstance(data, list):
        return [_esi_to_python(item) for item in data]
    if isinstance(data, dict):
        return {key: _esi_to_python(value) for key, value in data.items()}
    return data


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
            detail = f"Error calling ESI ({self.response_code})"
            if self.response is not None:
                return f"{detail}: {self.response}"
            return detail
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
        """Return a django-esi Token after validating/refreshing its access token.

        OpenAPI fleet (and other rate-limited) operations require the Token
        object so django-esi can read ``token.character_id`` for rate buckets.
        Callers that use raw ``requests`` must pass
        ``token.valid_access_token()`` in the Authorization header.
        """
        if not self.character_id:
            return None, NO_CLIENT_CHAR

        if self.character_esi_suspended:
            return None, CHAR_ESI_SUSPENDED

        token = Token.get_token(self.character_id, required_scopes)
        if not token:
            return None, NO_VALID_ESI_TOKEN

        try:
            token.valid_access_token()
            return token, SUCCESS
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

    @staticmethod
    def _bearer_headers(token: Token) -> dict:
        return {"Authorization": f"Bearer {token.valid_access_token()}"}

    @staticmethod
    def _http_response(
        result: EsiHttpResult, *, keep_error_text: bool = False
    ) -> EsiResponse:
        """The usual mapping for a raw call: SUCCESS with data, the HTTP
        status on a 4xx/5xx, ERROR_CALLING_ESI when the request raised."""
        if result.status is None or (
            result.error is not None and result.status < 400
        ):
            return EsiResponse(
                response_code=ERROR_CALLING_ESI, response=result.error
            )
        if result.status >= 400:
            return EsiResponse(
                response_code=result.status,
                response=result.text if keep_error_text else None,
            )
        return EsiResponse(response_code=SUCCESS, data=result.data)

    def _raw_get(
        self,
        path: str,
        required_scopes: List[str] | None = None,
        *,
        params: dict | None = None,
        paged: bool = False,
        empty=None,
    ) -> EsiResponse:
        """GET a route the OpenAPI client does not cover.

        With ``required_scopes`` the character's token is sent; without, the
        route is public. ``paged=True`` follows X-Pages.
        """
        access_token = None
        if required_scopes:
            token, status = self._valid_token(required_scopes)
            if status > 0:
                return EsiResponse(status)
            access_token = token.valid_access_token()
        return self._http_response(
            esi_request(
                "GET",
                path,
                access_token=access_token,
                params=params,
                paged=paged,
                empty=empty,
            )
        )

    def _operation_results(self, operation, **kwargs) -> EsiResponse:
        # django-esi raises HTTPNotModified on 304 instead of returning the
        # cached body, which surfaces as opaque 906. Default off for sync paths.
        kwargs.setdefault("use_etag", False)
        try:
            return EsiResponse(
                response_code=SUCCESS,
                data=_esi_to_python(operation.results(**kwargs)),
            )
        except (InvalidGrantError, TokenInvalidError) as e:
            logger.info(
                "ESI operation.results() token invalid for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        except HTTPClientError as e:
            logger.warning(
                "ESI operation.results() failed for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=e.status_code, response=e)
        except ESIErrorLimitException as e:
            logger.warning(
                "ESI operation.results() error-limited for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=420, response=e)
        except Exception as e:
            logger.warning(
                "ESI operation.results() failed for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def _operation_result(self, operation, **kwargs) -> EsiResponse:
        # See _operation_results — same 304/ETag pitfall for single-object ops.
        kwargs.setdefault("use_etag", False)
        try:
            data = _esi_to_python(operation.result(**kwargs))
            # Belt-and-suspenders: some operations return a one-element list
            # instead of the single dict callers expect.
            if (
                isinstance(data, list)
                and len(data) == 1
                and isinstance(data[0], dict)
            ):
                data = data[0]
            return EsiResponse(
                response_code=SUCCESS,
                data=data,
            )
        except (InvalidGrantError, TokenInvalidError) as e:
            logger.info(
                "ESI operation.result() token invalid for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)
        except HTTPClientError as e:
            logger.warning(
                "ESI operation.result() failed for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=e.status_code, response=e)
        except ESIErrorLimitException as e:
            logger.warning(
                "ESI operation.result() error-limited for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=420, response=e)
        except Exception as e:
            logger.warning(
                "ESI operation.result() failed for %s: %s",
                getattr(
                    getattr(operation, "operation", None), "operationId", None
                ),
                e,
            )
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_character_public_data(self, char_id: int) -> EsiResponse:
        """Returns the public data for the specified Eve character."""
        operation = esi_provider.client.Character.GetCharactersDetail(
            character_id=char_id
        )
        # Single-object endpoint: result(), not results().
        return self._operation_result(operation)

    def get_character_corporation_history(
        self, character_id: int
    ) -> EsiResponse:
        """Public ESI corporation membership history for a character (no token)."""
        operation = esi_provider.client.Character.GetCharactersCharacterIdCorporationhistory(
            character_id=character_id
        )
        return self._operation_results(operation)

    def get_corporation_alliance_history(
        self, corporation_id: int
    ) -> EsiResponse:
        """Public ESI alliance history for a corporation (no token)."""
        operation = esi_provider.client.Corporation.GetCorporationsCorporationIdAlliancehistory(
            corporation_id=corporation_id
        )
        return self._operation_results(operation)

    def get_character_skills(self) -> EsiResponse:
        """Returns the skills for the character this ESI client was created for."""

        token, status = self._valid_token(["esi-skills.read_skills.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Skills.GetCharactersCharacterIdSkills(
            character_id=self.character_id,
            token=token,
        )

        try:
            data = _esi_to_python(operation.result(use_etag=False))
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

        operation = esi_provider.client.Assets.GetCharactersCharacterIdAssets(
            character_id=self.character_id,
            token=token,
        )
        try:
            return EsiResponse(
                data=_esi_to_python(operation.results(use_etag=False)),
                response_code=SUCCESS,
            )
        except Exception as e:
            return EsiResponse(response_code=ERROR_CALLING_ESI, response=e)

    def get_recent_killmails(self) -> EsiResponse:
        """Returns a character's recent killmails"""

        token, status = self._valid_token(["esi-killmails.read_killmails.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Killmails.GetCharactersCharacterIdKillmailsRecent(
            character_id=self.character_id,
            token=token,
        )

        return self._operation_results(operation)

    def get_character_killmail(
        self, killmail_id, killmail_hash
    ) -> EsiResponse:
        """Returns a character's killmail"""
        operation = (
            esi_provider.client.Killmails.GetKillmailsKillmailIdKillmailHash(
                killmail_id=killmail_id, killmail_hash=killmail_hash
            )
        )
        # Single-object endpoint: result(), not results().
        return self._operation_result(operation)

    def get_character_blueprints(self) -> EsiResponse:
        """
        Returns all blueprints for the character. Paginated; fetches all pages.
        Requires esi-characters.read_blueprints.v1.
        """
        return self._raw_get(
            f"/characters/{self.character_id}/blueprints/",
            ["esi-characters.read_blueprints.v1"],
            paged=True,
        )

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

        operation = (
            esi_provider.client.Industry.GetCharactersCharacterIdIndustryJobs(
                character_id=self.character_id,
                token=token,
                include_completed=include_completed,
            )
        )
        try:
            jobs = _esi_to_python(operation.results(use_etag=False))
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

        operation = (
            esi_provider.client.Contracts.GetCharactersCharacterIdContracts(
                character_id=self.character_id,
                token=token,
            )
        )
        return self._operation_results(operation)

    def get_character_orders(self) -> EsiResponse:
        """Open market orders for this character (personal wallet)."""
        token, status = self._valid_token(
            ["esi-markets.read_character_orders.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Market.GetCharactersCharacterIdOrders(
            character_id=self.character_id,
            token=token,
        )
        return self._operation_results(operation)

    def get_corporation_orders(self, corporation_id: int) -> EsiResponse:
        """Open market orders placed on behalf of a corporation."""
        token, status = self._valid_token(
            ["esi-markets.read_corporation_orders.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = (
            esi_provider.client.Market.GetCorporationsCorporationIdOrders(
                corporation_id=corporation_id,
                token=token,
            )
        )
        return self._operation_results(operation)

    def get_corporation_contracts(self, corporation_id) -> EsiResponse:
        token, status = self._valid_token(
            ["esi-contracts.read_corporation_contracts.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Contracts.GetCorporationsCorporationIdContracts(
            corporation_id=corporation_id,
            token=token,
        )

        # Disable ETag — django-esi raises HTTPNotModified on 304 instead of
        # returning cached body, which would surface as opaque 906.
        return self._operation_results(operation, use_etag=False)

    def get_corporation_blueprints(self, corporation_id: int) -> EsiResponse:
        """
        Returns all blueprints for the corporation. Paginated; fetches all pages.
        Requires esi-corporations.read_blueprints.v1 (Director).
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/blueprints/",
            ["esi-corporations.read_blueprints.v1"],
            paged=True,
        )

    def get_corporation_industry_jobs(
        self, corporation_id: int, include_completed: bool = True
    ) -> EsiResponse:
        """
        Returns industry jobs for the corporation. Paginated; fetches all pages.
        Requires esi-industry.read_corporation_jobs.v1 (e.g. Factory_Manager).
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/industry/jobs/",
            ["esi-industry.read_corporation_jobs.v1"],
            params={"include_completed": include_completed},
            paged=True,
        )

    def get_corporation_wallet_journal_all_divisions(
        self, corporation_id: int
    ) -> EsiResponse:
        """
        Fetches all wallet journal entries for all divisions (1-7), all pages.
        Requires esi-wallet.read_corporation_wallets.v1.
        Returns EsiResponse with data = flat list, each entry tagged with
        its ``division``.
        """
        all_entries = []
        for division in range(1, 8):
            response = self._raw_get(
                f"/corporations/{corporation_id}/wallets/{division}/journal/",
                ["esi-wallet.read_corporation_wallets.v1"],
                paged=True,
            )
            if not response.success():
                return response
            for entry in response.data:
                entry["division"] = division
            all_entries.extend(response.data)

        return EsiResponse(response_code=SUCCESS, data=all_entries)

    def get_corporation_assets(self, corporation_id: int) -> EsiResponse:
        """
        All corporation assets (paginated). Requires
        esi-assets.read_corporation_assets.v1.
        """
        token, status = self._valid_token(
            ["esi-assets.read_corporation_assets.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = (
            esi_provider.client.Assets.GetCorporationsCorporationIdAssets(
                corporation_id=corporation_id,
                token=token,
            )
        )
        return self._operation_results(operation, use_etag=False)

    def get_corporation_wallets(self, corporation_id: int) -> EsiResponse:
        """
        Corporation wallet balances for divisions 1–7.
        Requires esi-wallet.read_corporation_wallets.v1
        (Accountant / Junior_Accountant).
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/wallets/",
            ["esi-wallet.read_corporation_wallets.v1"],
            empty=[],
        )

    def get_corporation_wallet_transactions(
        self, corporation_id: int
    ) -> EsiResponse:
        """
        Market wallet transactions for divisions 1–7.
        Requires esi-wallet.read_corporation_wallets.v1.
        """
        all_entries: list = []
        for division in range(1, 8):
            response = self._raw_get(
                f"/corporations/{corporation_id}/"
                f"wallets/{division}/transactions/",
                ["esi-wallet.read_corporation_wallets.v1"],
                empty=[],
            )
            if not response.success():
                return response
            for entry in response.data:
                entry["division"] = division
                all_entries.append(entry)

        return EsiResponse(response_code=SUCCESS, data=all_entries)

    def get_public_contracts(self, region_id) -> EsiResponse:
        operation = esi_provider.client.Contracts.GetContractsPublicRegionId(
            region_id=region_id,
        )

        return self._operation_results(operation)

    def get_public_contract_items(self, contract_id: int) -> EsiResponse:
        operation = (
            esi_provider.client.Contracts.GetContractsPublicItemsContractId(
                contract_id=contract_id,
            )
        )
        return self._operation_results(operation)

    def get_character_contract_items(self, contract_id: int) -> EsiResponse:
        token, status = self._valid_token(
            ["esi-contracts.read_character_contracts.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Contracts.GetCharactersCharacterIdContractsContractIdItems(
            character_id=self.character_id,
            contract_id=contract_id,
            token=token,
        )
        return self._operation_results(operation)

    def get_corporation_contract_items(
        self, corporation_id: int, contract_id: int
    ) -> EsiResponse:
        token, status = self._valid_token(
            ["esi-contracts.read_corporation_contracts.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Contracts.GetCorporationsCorporationIdContractsContractIdItems(
            corporation_id=corporation_id,
            contract_id=contract_id,
            token=token,
        )
        # Same 304/ETag pitfall as get_corporation_contracts.
        return self._operation_results(operation, use_etag=False)

    def get_region_market_history(
        self, region_id: int, type_id: int
    ) -> EsiResponse:
        """
        Fetch daily market history for a type in a region (public endpoint).
        Returns list of dicts with date, average, highest, lowest, order_count, volume.
        """
        response = self._raw_get(
            f"/markets/{region_id}/history/",
            params={"type_id": type_id},
            empty=[],
        )
        if response.response_code == ERROR_CALLING_ESI:
            logger.warning(
                "ESI request failed for region %s type %s: %s",
                region_id,
                type_id,
                response.response,
            )
        return response

    def get_structure_market_orders_page(
        self, structure_id: int, page: int
    ) -> EsiResponse:
        """
        Fetch a single page of structure market orders (1-based page number).
        """
        token, status = self._valid_token(["esi-markets.structure_markets.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Market.GetMarketsStructuresStructureId(
            structure_id=structure_id,
            page=page,
            token=token,
        )
        return self._operation_result(operation)

    def get_structure_market_orders_pages(self, structure_id: int):
        """
        Yields all market orders for the structure in one chunk (requires
        character with esi-markets.structure_markets.v1 and docking access).
        Uses django-esi's results(), which fetches all pages internally.
        Yields None once if token is invalid.
        """
        logger.info(
            "get_structure_market_orders_pages: structure_id=%s character_id=%s — fetching all pages via results()",
            structure_id,
            self.character_id,
        )
        token, status = self._valid_token(["esi-markets.structure_markets.v1"])
        if status > 0:
            logger.warning(
                "get_structure_market_orders_pages: structure_id=%s — invalid token (status=%s), yielding None",
                structure_id,
                status,
            )
            yield None
            return

        operation = esi_provider.client.Market.GetMarketsStructuresStructureId(
            structure_id=structure_id,
            token=token,
        )
        all_orders = _esi_to_python(operation.results(use_etag=False))
        count = len(all_orders) if all_orders else 0
        logger.info(
            "get_structure_market_orders_pages: structure_id=%s — received all pages, orders_count=%s",
            structure_id,
            count,
        )
        if all_orders:
            yield all_orders

    def get_active_fleet(self) -> EsiResponse:
        """The fleet the character is in. ``data`` keeps ESI's error body
        on a 4xx (e.g. "Character is not in a fleet")."""
        token, status = self._valid_token(["esi-fleets.read_fleet.v1"])
        if status > 0:
            return EsiResponse(status)

        result = esi_request(
            "GET",
            f"/characters/{self.character_id}/fleet/",
            access_token=token.valid_access_token(),
            timeout=10,
        )
        if result.status is None:
            return EsiResponse(
                response_code=ERROR_CALLING_ESI, response=result.error
            )
        return EsiResponse(response_code=result.status, data=result.data)

    def get_fleet_members(self, fleet_id: int) -> EsiResponse:
        token, status = self._valid_token(["esi-fleets.read_fleet.v1"])
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.GetFleetsFleetIdMembers(
            fleet_id=fleet_id, token=token
        )

        return self._operation_results(operation)

    def get_alliance(self, alliance_id: int) -> EsiResponse:
        operation = esi_provider.client.Alliance.GetAlliancesAllianceId(
            alliance_id=alliance_id
        )
        # Single-object endpoint: result(), not results() (which returns a list)
        return self._operation_result(operation)

    def get_alliance_corporations(self, alliance_id: int) -> EsiResponse:
        operation = (
            esi_provider.client.Alliance.GetAlliancesAllianceIdCorporations(
                alliance_id=alliance_id
            )
        )
        return self._operation_results(operation)

    def get_corporation(self, corporation_id: int) -> EsiResponse:
        operation = (
            esi_provider.client.Corporation.GetCorporationsCorporationId(
                corporation_id=corporation_id
            )
        )
        # Single-object endpoint: result(), not results() (which returns a list)
        return self._operation_result(operation)

    def get_corporation_members(self, corporation_id: int) -> EsiResponse:
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Corporation.GetCorporationsCorporationIdMembers(
            corporation_id=corporation_id,
            token=token,
        )

        return self._operation_results(operation)

    def get_corporation_roles(self, corporation_id: int) -> EsiResponse:
        """
        Returns roles of all corporation members. Paginated; fetches all pages.
        Requires Personnel_Manager or grantable role (esi-corporations.read_corporation_membership.v1).
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/roles/",
            ["esi-corporations.read_corporation_membership.v1"],
            paged=True,
        )

    def get_corporation_titles(self, corporation_id: int) -> EsiResponse:
        """
        Returns corporation title definitions (roles granted by each title).
        Requires esi-corporations.read_titles.v1.
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/titles/",
            ["esi-corporations.read_titles.v1"],
            paged=True,
        )

    def get_corporation_member_titles(
        self, corporation_id: int
    ) -> EsiResponse:
        """
        Returns title ids held by each corporation member.
        Requires esi-corporations.read_titles.v1.
        """
        return self._raw_get(
            f"/corporations/{corporation_id}/members/titles/",
            ["esi-corporations.read_titles.v1"],
            paged=True,
        )

    def send_evemail(self, mail_details) -> EsiResponse:
        required_scopes = ["esi-mail.send_mail.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Mail.PostCharactersCharacterIdMail(
            body=mail_details,
            character_id=self.character_id,
            token=token,
        )

        return self._operation_results(operation)

    def search_category(self, category: str, search: str) -> EsiResponse:
        """Prefix search via GET /characters/{id}/search/.

        ``esi-search.search_structures.v1`` is the scope ESI requires for
        corporation and alliance searches, despite the name.
        """
        if not live_esi_allowed():
            return EsiResponse(ERROR_CALLING_ESI)
        token, status = self._valid_token(["esi-search.search_structures.v1"])
        if status > 0:
            return EsiResponse(status)

        result = esi_request(
            "GET",
            f"/characters/{self.character_id}/search/",
            access_token=token.valid_access_token(),
            params={
                "categories": category,
                "search": search,
                "strict": "false",
            },
            timeout=10,
        )
        if result.status is None:
            return EsiResponse(
                response_code=ERROR_CALLING_ESI, response=result.error, data={}
            )
        data = result.data if isinstance(result.data, dict) else {}
        return EsiResponse(response_code=result.status, data=data)

    def resolve_universe_names(self, ids_to_resolve) -> EsiResponse:
        if not live_esi_allowed():
            return EsiResponse(ERROR_CALLING_ESI)
        operation = esi_provider.client.Universe.PostUniverseNames(
            body=ids_to_resolve
        )
        return self._operation_results(operation)

    def resolve_universe_ids(self, names) -> EsiResponse:
        """Exact names -> ids (POST /universe/ids/, at most 500 names)."""
        if not live_esi_allowed():
            return EsiResponse(ERROR_CALLING_ESI)
        operation = esi_provider.client.Universe.PostUniverseIds(body=names)
        # Single-object endpoint: results() would wrap it in a list.
        return self._operation_result(operation)

    def get_fleet(self, fleet_id) -> EsiResponse:
        required_scopes = ["esi-fleets.read_fleet.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.GetFleetsFleetId(
            fleet_id=fleet_id,
            token=token,
        )

        # Single-object endpoint: result(), not results().
        # Disable ETag — django-esi raises HTTPNotModified on 304 instead of
        # returning cached body, which would surface as opaque 906.
        return self._operation_result(operation, use_etag=False)

    def update_fleet_details(self, fleet_id, update) -> EsiResponse:
        required_scopes = ["esi-fleets.write_fleet.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Fleets.PutFleetsFleetId(
            fleet_id=fleet_id,
            body=update,
            token=token,
        )

        # 204 No Content: result(), not results() (which wraps None as [None])
        return self._operation_result(operation, use_etag=False)

    def set_autopilot_waypoint(
        self, destination_id: int, clear_other_waypoints: bool = True
    ) -> EsiResponse:
        """Sets the in-game destination (POST /ui/autopilot/waypoint/).

        A UI write: callers send it only on the pilot's own click.
        """
        token, status = self._valid_token(["esi-ui.write_waypoint.v1"])
        if status > 0:
            return EsiResponse(status)

        assert_esi_http_allowed()
        result = esi_request(
            "POST",
            "/ui/autopilot/waypoint/",
            access_token=token.valid_access_token(),
            params={
                "add_to_beginning": "false",
                "clear_other_waypoints": (
                    "true" if clear_other_waypoints else "false"
                ),
                "destination_id": int(destination_id),
            },
            timeout=15,
        )
        if result.status is None:
            return EsiResponse(
                response_code=ERROR_CALLING_ESI, response=result.error
            )
        if result.status == 204:
            return EsiResponse(response_code=SUCCESS)
        return EsiResponse(response_code=result.status)

    def get_character_planets(self) -> EsiResponse:
        """Returns the list of planetary colonies for the character."""
        return self._raw_get(
            f"/characters/{self.character_id}/planets/",
            ["esi-planets.manage_planets.v1"],
        )

    def get_character_planet_details(self, planet_id: int) -> EsiResponse:
        """Returns the full layout (pins, routes, links) for a character's planet colony."""
        return self._raw_get(
            f"/characters/{self.character_id}/planets/{planet_id}/",
            ["esi-planets.manage_planets.v1"],
        )

    def get_universe_schematic(self, schematic_id: int) -> EsiResponse:
        """
        Returns PI schematic info (cycle_time, schematic_name).

        Public endpoint; no auth required. Cached by ESI for up to 3600 seconds.
        """
        return self._raw_get(f"/universe/schematics/{schematic_id}/")

    def get_character_clones(self) -> EsiResponse:
        """Returns jump clones and medical clone location for the character."""
        return self._raw_get(
            f"/characters/{self.character_id}/clones/",
            ["esi-clones.read_clones.v1"],
        )

    def get_character_implants(self) -> EsiResponse:
        """Returns active implant type IDs for the character."""
        return self._raw_get(
            f"/characters/{self.character_id}/implants/",
            ["esi-clones.read_implants.v1"],
        )

    def get_character_mining_ledger(self) -> EsiResponse:
        """Returns the personal mining ledger for the character (last 30
        days). Paginated; fetches all pages."""
        return self._raw_get(
            f"/characters/{self.character_id}/mining/",
            ["esi-industry.read_character_mining.v1"],
            paged=True,
        )

    def get_character_notifications(self) -> EsiResponse:
        """Returns recent notifications for the character"""

        token, status = self._valid_token(
            ["esi-characters.read_notifications.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        # Use direct call as Swagger validation fails. The requests response
        # stays attached so callers can read ESI budget headers, including
        # on a 200. A 304 has no body. Callers account the call against the
        # char-notification bucket themselves, so the transport does not.
        headers = {}
        etag = esi_budget.notification_etag(self.character_id)
        if etag:
            headers["If-None-Match"] = etag

        result = esi_request(
            "GET",
            f"/characters/{self.character_id}/notifications/",
            access_token=token.valid_access_token(),
            headers=headers,
            timeout=10,
            account=False,
        )
        if result.status is None:
            return EsiResponse(
                response_code=ERROR_CALLING_ESI, response=result.error
            )
        if result.status == 304:
            return EsiResponse(response_code=304, response=result.response)
        if result.status == 200 and result.error is None:
            return EsiResponse(
                response_code=200, data=result.data, response=result.response
            )
        return EsiResponse(
            response_code=result.status,
            data=result.text,
            response=result.response,
        )

    def get_character_affiliations(self, character_ids) -> EsiResponse:
        """
        Returns the affiliations for a batch of characters.
        """
        operation = esi_provider.client.Character.PostCharactersAffiliation(
            body=character_ids
        )
        return self._operation_results(operation)

    def get_character_fw_stats(self) -> EsiResponse:
        """Return FW stats for the authenticated character."""
        required_scopes = ["esi-characters.read_fw_stats.v1"]
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Faction_Warfare.GetCharactersCharacterIdFwStats(
            character_id=self.character_id,
            token=token,
        )
        # Single-object endpoint: result(), not results().
        return self._operation_result(operation)

    def _authenticated_esi_request(
        self,
        method: str,
        url: str,
        required_scopes: List[str],
        json_body=None,
    ) -> EsiResponse:
        """
        Call an authenticated ESI route the OpenAPI client does not cover
        (e.g. fittings) with the Equinox compatibility date. ``data`` holds
        the JSON body when the response has one (204 -> None).
        """
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)

        return self._http_response(
            esi_request(
                method,
                url,
                access_token=token.valid_access_token(),
                json_body=json_body,
                compat=True,
            ),
            keep_error_text=True,
        )

    # --- character fittings (no OpenAPI tag in django-esi) -------------------

    def create_character_fitting(self, fitting: dict) -> EsiResponse:
        """
        Save a fitting under the character. ``fitting`` is the ESI body:
        ``{"name", "description", "ship_type_id", "items": [{"type_id",
        "flag", "quantity"}]}``; ``data["fitting_id"]`` on success.
        """
        return self._authenticated_esi_request(
            "POST",
            f"{ESI_BASE_URL}/characters/{self.character_id}/fittings/",
            ["esi-fittings.write_fittings.v1"],
            json_body=fitting,
        )

    def delete_character_fitting(self, fitting_id: int) -> EsiResponse:
        """Delete one of the character's saved fittings."""
        return self._authenticated_esi_request(
            "DELETE",
            f"{ESI_BASE_URL}/characters/{self.character_id}/fittings/{fitting_id}/",
            ["esi-fittings.write_fittings.v1"],
        )

    # --- corporation projects (no OpenAPI tag in django-esi) ----------------

    def _cursor_walk(
        self, url: str, required_scopes: List[str], key: str, params=None
    ) -> EsiResponse:
        """
        Walk an ESI cursor-paginated route from the newest record backwards
        until a page comes back empty. ``data`` is every row under ``key``.
        """
        token, status = self._valid_token(required_scopes)
        if status > 0:
            return EsiResponse(status)
        access_token = token.valid_access_token()
        rows = []
        before = None
        for _ in range(MAX_CURSOR_PAGES):
            query = {**(params or {}), "limit": 100}
            if before:
                query["before"] = before
            result = esi_request(
                "GET",
                url,
                access_token=access_token,
                params=query,
                compat=True,
                empty={},
            )
            if not result.ok:
                return self._http_response(result, keep_error_text=True)
            body = result.data or {}
            page = body.get(key) or []
            rows.extend(page)
            next_before = (body.get("cursor") or {}).get("before")
            if not page or not next_before or next_before == before:
                break
            before = next_before
        return EsiResponse(response_code=SUCCESS, data=rows)

    def get_corporation_projects(
        self, corporation_id: int, state: str = "All"
    ) -> EsiResponse:
        """Every project of the corporation (``state`` All or Active)."""
        return self._cursor_walk(
            f"{ESI_BASE_URL}/corporations/{corporation_id}/projects",
            SCOPE_CORPORATION_PROJECTS,
            "projects",
            params={"state": state},
        )

    def get_corporation_project(
        self, corporation_id: int, project_id: str
    ) -> EsiResponse:
        """One project with its configuration, reward and dates."""
        return self._authenticated_esi_request(
            "GET",
            f"{ESI_BASE_URL}/corporations/{corporation_id}"
            f"/projects/{project_id}",
            SCOPE_CORPORATION_PROJECTS,
        )

    def get_corporation_project_contributors(
        self, corporation_id: int, project_id: str
    ) -> EsiResponse:
        """Each contributor's total progress. Needs the Project_Manager
        role in game, which CEOs and directors hold."""
        return self._cursor_walk(
            f"{ESI_BASE_URL}/corporations/{corporation_id}"
            f"/projects/{project_id}/contributors",
            SCOPE_CORPORATION_PROJECTS,
            "contributors",
        )

    def get_corp_structures(self, corp_id: int) -> EsiResponse:
        """
        Returns all the structures owned by a corp
        """
        token, status = self._valid_token(
            ["esi-corporations.read_structures.v1"]
        )
        if status > 0:
            return EsiResponse(status)

        operation = esi_provider.client.Corporation.GetCorporationsCorporationIdStructures(
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

    Stops after the last page ESI reports in X-Pages. Without the header it
    falls back to stopping on a short page.
    """
    logger.info(
        "get_region_market_orders_pages: region_id=%s type_id=%s — starting",
        region_id,
        type_id,
    )
    page = 1
    page_size = 1000
    params: dict = {"page": page}
    if type_id is not None:
        params["type_id"] = type_id
    while True:
        logger.info(
            "get_region_market_orders_pages: region_id=%s — requesting page %s",
            region_id,
            page,
        )
        result = esi_request(
            "GET", f"/markets/{region_id}/orders/", params=params, empty=[]
        )
        if result.status is None:
            logger.warning(
                "ESI request failed for region %s page %s: %s",
                region_id,
                page,
                result.error,
            )
            yield None
            return
        if not result.ok:
            logger.warning(
                "get_region_market_orders_pages: region_id=%s page=%s — status %s",
                region_id,
                page,
                result.status,
            )
            yield None
            return
        page_data = result.data or []
        logger.info(
            "get_region_market_orders_pages: region_id=%s — page %s received, orders_count=%s",
            region_id,
            page,
            len(page_data),
        )
        if not page_data:
            break
        yield page_data
        total_pages = result.headers.get("X-Pages")
        try:
            last_page = page >= int(total_pages)
        except (TypeError, ValueError):
            last_page = len(page_data) < page_size
        if last_page:
            break
        page += 1
        params["page"] = page


def esi_for(character) -> EsiClient:
    """
    Returns an ESI client for the specified character.

    The saved auth token for the character will be used.

    The client might be a mock if configured for mocking in settings.py
    """
    if mock_esi_enabled():
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
