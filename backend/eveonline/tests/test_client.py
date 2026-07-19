from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from eveonline.client import (
    ERROR_CALLING_ESI,
    SUCCESS,
    EsiClient,
    EsiResponse,
)


class EsiClientTest(SimpleTestCase):
    """Test what we can of the EsiClient"""

    def test_response_error(self):
        response = EsiResponse(response_code=500, data="Boom!")

        self.assertRaises(ValueError, response.results)

    @patch("eveonline.client.Token.get_token")
    def test_valid_token_returns_token_object(self, get_token_mock):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        # pylint: disable-next=protected-access
        result, status = client._valid_token(["esi-fleets.write_fleet.v1"])

        self.assertEqual(status, SUCCESS)
        self.assertIs(result, token)
        token.valid_access_token.assert_called_once()

    def test_bearer_headers_uses_access_token_string(self):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"

        # pylint: disable-next=protected-access
        headers = EsiClient._bearer_headers(token)

        self.assertEqual(
            headers, {"Authorization": "Bearer access-token-string"}
        )

    @patch("eveonline.client.Token.get_token")
    def test_get_corporation_contracts_disables_etag(self, get_token_mock):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        operation = MagicMock()
        contracts = MagicMock()
        contracts.GetCorporationsCorporationIdContracts.return_value = (
            operation
        )

        with patch("eveonline.client.esi_provider") as provider, patch.object(
            EsiClient,
            "_operation_results",
            return_value=EsiResponse(SUCCESS),
        ) as op_results:
            provider.client.Contracts = contracts
            response = client.get_corporation_contracts(98705678)

        contracts.GetCorporationsCorporationIdContracts.assert_called_once_with(
            corporation_id=98705678,
            token=token,
        )
        op_results.assert_called_once_with(operation, use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)

    @patch("eveonline.client.Token.get_token")
    def test_get_corporation_contract_items_disables_etag(
        self, get_token_mock
    ):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        operation = MagicMock()
        contracts = MagicMock()
        contracts.GetCorporationsCorporationIdContractsContractIdItems.return_value = (
            operation
        )

        with patch("eveonline.client.esi_provider") as provider, patch.object(
            EsiClient,
            "_operation_results",
            return_value=EsiResponse(SUCCESS),
        ) as op_results:
            provider.client.Contracts = contracts
            response = client.get_corporation_contract_items(98705678, 123)

        contracts.GetCorporationsCorporationIdContractsContractIdItems.assert_called_once_with(
            corporation_id=98705678,
            contract_id=123,
            token=token,
        )
        op_results.assert_called_once_with(operation, use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)

    @patch("eveonline.client.Token.get_token")
    def test_update_fleet_details_passes_token_object(self, get_token_mock):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        operation = MagicMock()
        fleets = MagicMock()
        fleets.PutFleetsFleetId.return_value = operation

        with patch("eveonline.client.esi_provider") as provider, patch.object(
            EsiClient,
            "_operation_result",
            return_value=EsiResponse(SUCCESS),
        ) as op_result:
            provider.client.Fleets = fleets
            response = client.update_fleet_details(
                1236712292315, {"motd": "hello"}
            )

        fleets.PutFleetsFleetId.assert_called_once_with(
            fleet_id=1236712292315,
            body={"motd": "hello"},
            token=token,
        )
        op_result.assert_called_once_with(operation, use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)

    def test_operation_results_defaults_use_etag_false(self):
        client = EsiClient(634915984)
        operation = MagicMock()
        operation.results.return_value = [{"contract_id": 1}]
        operation.operation.operationId = "GetCharactersCharacterIdContracts"

        # pylint: disable-next=protected-access
        response = client._operation_results(operation)

        operation.results.assert_called_once_with(use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.results(), [{"contract_id": 1}])

    def test_operation_result_defaults_use_etag_false(self):
        client = EsiClient(634915984)
        operation = MagicMock()
        operation.result.return_value = {"fleet_id": 1}
        operation.operation.operationId = "GetFleetsFleetId"

        # pylint: disable-next=protected-access
        response = client._operation_result(operation)

        operation.result.assert_called_once_with(use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.results(), {"fleet_id": 1})

    @patch("eveonline.client.Token.get_token")
    def test_get_character_contracts_uses_operation_results(
        self, get_token_mock
    ):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        operation = MagicMock()
        contracts = MagicMock()
        contracts.GetCharactersCharacterIdContracts.return_value = operation

        with patch("eveonline.client.esi_provider") as provider, patch.object(
            EsiClient,
            "_operation_results",
            return_value=EsiResponse(SUCCESS, data=[]),
        ) as op_results:
            provider.client.Contracts = contracts
            response = client.get_character_contracts()

        contracts.GetCharactersCharacterIdContracts.assert_called_once_with(
            character_id=634915984,
            token=token,
        )
        # Wrapper applies use_etag=False; callers need not pass it.
        op_results.assert_called_once_with(operation)
        self.assertEqual(response.response_code, SUCCESS)

    @patch("eveonline.client.Token.get_token")
    def test_get_character_assets_disables_etag(self, get_token_mock):
        token = MagicMock()
        token.valid_access_token.return_value = "access-token-string"
        token.character_id = 634915984
        get_token_mock.return_value = token

        client = EsiClient(634915984)
        operation = MagicMock()
        operation.results.return_value = [{"item_id": 1}]
        assets = MagicMock()
        assets.GetCharactersCharacterIdAssets.return_value = operation

        with patch("eveonline.client.esi_provider") as provider:
            provider.client.Assets = assets
            response = client.get_character_assets()

        operation.results.assert_called_once_with(use_etag=False)
        self.assertEqual(response.response_code, SUCCESS)
        self.assertEqual(response.results(), [{"item_id": 1}])

    def test_operation_result_preserves_underlying_exception(self):
        client = EsiClient(634915984)
        operation = MagicMock()
        operation.result.side_effect = AttributeError(
            "'str' object has no attribute 'character_id'"
        )
        operation.operation.operationId = "PutFleetsFleetId"

        # pylint: disable-next=protected-access
        response = client._operation_result(operation)

        self.assertEqual(response.response_code, ERROR_CALLING_ESI)
        self.assertIsInstance(response.response, AttributeError)
        self.assertIn("character_id", str(response.response))
        operation.result.assert_called_once_with(use_etag=False)
