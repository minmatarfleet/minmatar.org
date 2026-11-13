"""Discord button payloads for hangar buyback purchase-order threads."""

COMPLETE_CUSTOM_ID_PREFIX = "buyback:complete:"
CANCEL_CUSTOM_ID_PREFIX = "buyback:cancel:"
CONTRACT_UP_CUSTOM_ID_PREFIX = "buyback:contract_up:"
CONTRACT_ACCEPTED_CUSTOM_ID_PREFIX = "buyback:contract_accepted:"
CLOSE_CUSTOM_ID_PREFIX = "buyback:close:"


def complete_custom_id(order_id: int) -> str:
    return f"{COMPLETE_CUSTOM_ID_PREFIX}{int(order_id)}"


def cancel_custom_id(order_id: int) -> str:
    return f"{CANCEL_CUSTOM_ID_PREFIX}{int(order_id)}"


def contract_up_custom_id(order_id: int) -> str:
    return f"{CONTRACT_UP_CUSTOM_ID_PREFIX}{int(order_id)}"


def contract_accepted_custom_id(order_id: int) -> str:
    return f"{CONTRACT_ACCEPTED_CUSTOM_ID_PREFIX}{int(order_id)}"


def close_custom_id(order_id: int) -> str:
    return f"{CLOSE_CUSTOM_ID_PREFIX}{int(order_id)}"


def _button(*, label: str, style: int, custom_id: str) -> dict:
    return {
        "type": 2,
        "style": style,
        "label": label,
        "custom_id": custom_id,
    }


def _row(*buttons: dict) -> list[dict]:
    return [{"type": 1, "components": list(buttons)}]


def contract_up_components(order_id: int) -> list[dict]:
    """Buyback team marks the in-game contract up. Cancel stays available."""
    return _row(
        _button(
            label="Contract up",
            style=3,
            custom_id=contract_up_custom_id(order_id),
        ),
        _button(
            label="Cancel",
            style=4,
            custom_id=cancel_custom_id(order_id),
        ),
    )


def contract_accepted_components(order_id: int) -> list[dict]:
    """Buyer confirms they accepted the contract. Cancel stays available."""
    return _row(
        _button(
            label="Contract accepted",
            style=3,
            custom_id=contract_accepted_custom_id(order_id),
        ),
        _button(
            label="Cancel",
            style=4,
            custom_id=cancel_custom_id(order_id),
        ),
    )


def close_components(order_id: int) -> list[dict]:
    """Buyback team closes a sale thread that predates Contract up."""
    return _row(
        _button(
            label="Close",
            style=2,
            custom_id=close_custom_id(order_id),
        )
    )


def order_action_components(order_id: int) -> list[dict]:
    """Buttons on a new sale thread: Contract up, then Cancel."""
    return contract_up_components(order_id)
