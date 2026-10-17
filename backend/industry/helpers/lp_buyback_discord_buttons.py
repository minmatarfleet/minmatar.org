"""Discord button payloads for LP buyback settlement acks."""

LP_SENT_CUSTOM_ID_PREFIX = "lp_buyback:lp:"
ISK_SENT_CUSTOM_ID_PREFIX = "lp_buyback:isk:"


def lp_sent_custom_id(order_id: int) -> str:
    return f"{LP_SENT_CUSTOM_ID_PREFIX}{int(order_id)}"


def isk_sent_custom_id(order_id: int) -> str:
    return f"{ISK_SENT_CUSTOM_ID_PREFIX}{int(order_id)}"


def _ack_button(*, label: str, custom_id: str) -> list[dict]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 3,
                    "label": label,
                    "custom_id": custom_id,
                }
            ],
        }
    ]


def lp_sent_components(order_id: int) -> list[dict]:
    return _ack_button(label="LP sent", custom_id=lp_sent_custom_id(order_id))


def isk_sent_components(order_id: int) -> list[dict]:
    return _ack_button(
        label="ISK sent", custom_id=isk_sent_custom_id(order_id)
    )
