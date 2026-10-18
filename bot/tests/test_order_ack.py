"""Both order desks' Discord acks hit their own URL with the same request."""

import unittest
from unittest.mock import MagicMock, patch


def _response(status_code, body=None, text=""):
    response = MagicMock(status_code=status_code, text=text)
    response.json.return_value = body
    return response


class OrderAckTestCase(unittest.TestCase):
    def test_each_desk_posts_to_its_own_url(self):
        # pylint: disable=import-outside-toplevel
        from app.buyback import service as buyback
        from app.lp_buyback import service as lp_buyback
        from app.settings import settings

        cases = [
            (buyback, f"{settings.API_URL}/buyback/stock/orders/7/discord-ack"),
            (lp_buyback, f"{settings.API_URL}/industry/loyalty/orders/7/discord-ack"),
        ]
        for module, url in cases:
            with patch("app.order_ack.requests.post") as post:
                post.return_value = _response(200, {"id": 7, "status": "completed"})
                result = module.discord_ack_order(7, action="complete", discord_user_id=99)
            self.assertEqual(7, result.id)
            self.assertEqual("completed", result.status)
            post.assert_called_once_with(
                url,
                headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
                json={"discord_user_id": 99, "action": "complete"},
                timeout=10,
            )

    def test_api_errors_carry_detail_and_status(self):
        # pylint: disable=import-outside-toplevel
        from app.lp_buyback.service import DiscordAckError, discord_ack_order

        with patch("app.order_ack.requests.post") as post:
            post.return_value = _response(403, {"detail": "Not your order"})
            with self.assertRaises(DiscordAckError) as ctx:
                discord_ack_order(7, action="isk_sent", discord_user_id=99)
        self.assertEqual("Not your order", str(ctx.exception))
        self.assertEqual(403, ctx.exception.status_code)

        with patch("app.order_ack.requests.post") as post:
            bad = _response(502, text="Bad gateway")
            bad.json.side_effect = ValueError("not json")
            post.return_value = bad
            with self.assertRaises(DiscordAckError) as ctx:
                discord_ack_order(7, action="isk_sent", discord_user_id=99)
        self.assertEqual("Bad gateway", str(ctx.exception))
