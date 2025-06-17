from unittest.mock import MagicMock

from django.utils import timezone

from eveonline.client import EsiClient, EsiResponse

esi_config = {"mock_esi": None}


def get_mock_esi(character=None):
    """
    Returns a mock ESI client

    The mocked client will be a pre-configured `unittest.mock.MagicMock`
    instance.
    """
    if not esi_config["mock_esi"]:
        esi_config["mock_esi"] = MagicMock(spec=EsiClient)
        configure_mock(esi_config["mock_esi"])
    return esi_config["mock_esi"]


def configure_mock(mock: MagicMock):
    """
    Configure the behaviour of the mock ESI client
    """
    configure_mock_notifications(mock)


def configure_mock_notifications(mock: MagicMock):
    mock.get_character_notifications.return_value = EsiResponse(
        response_code=200,
        data=[
            {
                "notification_id": 3786348736,
                "type": "StructureUnderAttack",
                "timestamp": timezone.now(),
                "text": "Test notification",
            }
        ],
    )
