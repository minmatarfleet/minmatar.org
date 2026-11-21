"""Help-ticket threads must show the whole report.

The modal accepts 2000 characters. An embed field stops at 1024, so a
field used to drop the rest with no error. The description holds 4096.
"""

import unittest

from app.tickets.modals import HelpRequestModal
from app.tickets.ticket_flow import EMBED_DESCRIPTION_MAX, ticket_detail_embeds


class TicketDetailEmbedsTestCase(unittest.TestCase):
    def test_longer_than_a_field_is_not_cut(self):
        body = "x" * 1025
        embeds = ticket_detail_embeds(body)
        self.assertEqual([body], [embed.description for embed in embeds])
        self.assertEqual([], embeds[0].fields)

    def test_modal_length_is_posted_in_full(self):
        modal_max = HelpRequestModal.details.max_length
        self.assertLessEqual(modal_max, EMBED_DESCRIPTION_MAX)
        body = "a" * modal_max
        embeds = ticket_detail_embeds(body)
        self.assertEqual(body, "".join(embed.description for embed in embeds))
        self.assertEqual(1, len(embeds))
        self.assertEqual("Details", embeds[0].title)

    def test_past_description_limit_continues_in_another_embed(self):
        body = "y" * (EMBED_DESCRIPTION_MAX + 1)
        embeds = ticket_detail_embeds(body)
        self.assertEqual(body, "".join(embed.description for embed in embeds))
        self.assertEqual(2, len(embeds))
        self.assertEqual("Details", embeds[0].title)
        self.assertIsNone(embeds[1].title)
        self.assertTrue(
            all(len(embed.description) <= EMBED_DESCRIPTION_MAX for embed in embeds)
        )

    def test_empty_body_posts_nothing(self):
        self.assertEqual([], ticket_detail_embeds(""))
