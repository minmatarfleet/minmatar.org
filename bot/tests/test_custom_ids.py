"""The button custom_ids the bot listens for.

Posted Discord messages keep their custom_ids, so these strings are a
persisted contract with every message already sent.
"""

import re
import unittest

from app import custom_ids

# What the bot matched before custom_ids.py existed. Never change these.
HISTORICAL_TEMPLATES = {
    "BUYBACK_COMPLETE_TEMPLATE": r"buyback:complete:(?P<order_id>[0-9]+)",
    "BUYBACK_CANCEL_TEMPLATE": r"buyback:cancel:(?P<order_id>[0-9]+)",
    "LP_BUYBACK_LP_SENT_TEMPLATE": r"lp_buyback:lp:(?P<order_id>[0-9]+)",
    "LP_BUYBACK_ISK_SENT_TEMPLATE": r"lp_buyback:isk:(?P<order_id>[0-9]+)",
    "NOTIF_ACK_TEMPLATE": r"notif_ack:(?P<delivery_id>[0-9]+)",
    "NPSI_POST_TEMPLATE": r"npsi:create:(?P<event_id>[0-9]+)",
    "NPSI_POST_ALIAS_TEMPLATE": r"npsi:post:(?P<event_id>[0-9]+)",
    "NPSI_PREPING_TEMPLATE": r"npsi:preping:(?P<event_id>[0-9]+)",
    "NPSI_TRACK_TEMPLATE": r"npsi:track:(?P<event_id>[0-9]+)",
    "TRIBE_INVITE_DECLINE_TEMPLATE": (
        r"tribe_invite:decline:(?P<invitation_id>[0-9]+)"
    ),
    "FLEET_INVITE_OUT_TEMPLATE": r"fleet_invite:out:(?P<invite_id>[0-9]+)",
    "HELP_TICKET_CLOSE_TEMPLATE": r"help_ticket_close:(?P<ticket_id>[0-9]+)",
    "HELP_TICKET_CLOSE_REASON_TEMPLATE": (
        r"help_ticket_close_reason:(?P<ticket_id>[0-9]+)"
    ),
}


class CustomIdContractTestCase(unittest.TestCase):
    def test_templates_never_change(self):
        for name, expected in HISTORICAL_TEMPLATES.items():
            self.assertEqual(expected, getattr(custom_ids, name), name)

    def test_every_prefix_round_trips_through_its_template(self):
        for name in HISTORICAL_TEMPLATES:
            prefix = getattr(custom_ids, name.replace("_TEMPLATE", "_PREFIX"))
            template = getattr(custom_ids, name)
            match = re.fullmatch(template, custom_ids.custom_id(prefix, 42))
            self.assertIsNotNone(match, name)
            self.assertEqual("42", match.groups()[0])

    def test_module_has_no_third_party_imports(self):
        """The backend loads this file by path without discord installed."""
        with open(custom_ids.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotRegex(source, r"^\s*(import|from)\s", "imports found")


class ViewsUseTheContractTestCase(unittest.TestCase):
    def test_dynamic_items_match_the_shared_templates(self):
        # pylint: disable=import-outside-toplevel
        from app.buyback.views import CancelButton, CompleteButton
        from app.lp_buyback.views import IskSentButton, LpSentButton
        from app.notifications.views import MarkAsReadButton
        from app.npsi.views import (
            PostToScheduleAliasButton,
            PostToScheduleButton,
            PrepingButton,
            TrackButton,
        )
        from app.tickets.views import CloseTicketButton, CloseWithReasonButton
        from app.fleet_invites.views import SitOutButton, StopInvitesButton
        from app.tribe_invites.views import DeclineInviteButton

        pairs = {
            CompleteButton: custom_ids.BUYBACK_COMPLETE_TEMPLATE,
            CancelButton: custom_ids.BUYBACK_CANCEL_TEMPLATE,
            LpSentButton: custom_ids.LP_BUYBACK_LP_SENT_TEMPLATE,
            IskSentButton: custom_ids.LP_BUYBACK_ISK_SENT_TEMPLATE,
            MarkAsReadButton: custom_ids.NOTIF_ACK_TEMPLATE,
            PostToScheduleButton: custom_ids.NPSI_POST_TEMPLATE,
            PostToScheduleAliasButton: custom_ids.NPSI_POST_ALIAS_TEMPLATE,
            PrepingButton: custom_ids.NPSI_PREPING_TEMPLATE,
            TrackButton: custom_ids.NPSI_TRACK_TEMPLATE,
            CloseTicketButton: custom_ids.HELP_TICKET_CLOSE_TEMPLATE,
            CloseWithReasonButton: custom_ids.HELP_TICKET_CLOSE_REASON_TEMPLATE,
            DeclineInviteButton: custom_ids.TRIBE_INVITE_DECLINE_TEMPLATE,
            SitOutButton: custom_ids.FLEET_INVITE_OUT_TEMPLATE,
            StopInvitesButton: custom_ids.FLEET_INVITE_STOP_TEMPLATE,
        }
        for item, template in pairs.items():
            compiled = item.__discord_ui_compiled_template__
            self.assertEqual(template, compiled.pattern, item.__name__)
