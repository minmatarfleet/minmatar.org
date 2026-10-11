"""Discord button payloads for hangar buyback purchase-order threads."""

COMPLETE_CUSTOM_ID_PREFIX = "buyback:complete:"
CANCEL_CUSTOM_ID_PREFIX = "buyback:cancel:"


def complete_custom_id(order_id: int) -> str:
    return f"{COMPLETE_CUSTOM_ID_PREFIX}{int(order_id)}"


def cancel_custom_id(order_id: int) -> str:
    return f"{CANCEL_CUSTOM_ID_PREFIX}{int(order_id)}"


def _parse_prefixed_id(custom_id: str, prefix: str) -> int | None:
    if not custom_id or not custom_id.startswith(prefix):
        return None
    raw = custom_id[len(prefix) :]
    return int(raw) if raw.isdigit() else None


def parse_complete_custom_id(custom_id: str) -> int | None:
    return _parse_prefixed_id(custom_id, COMPLETE_CUSTOM_ID_PREFIX)


def parse_cancel_custom_id(custom_id: str) -> int | None:
    return _parse_prefixed_id(custom_id, CANCEL_CUSTOM_ID_PREFIX)


def order_action_components(order_id: int) -> list[dict]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 3,
                    "label": "Complete",
                    "custom_id": complete_custom_id(order_id),
                },
                {
                    "type": 2,
                    "style": 4,
                    "label": "Cancel",
                    "custom_id": cancel_custom_id(order_id),
                },
            ],
        }
    ]
