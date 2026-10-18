from unittest.mock import patch

from django.test import TestCase

from buyback.helpers.counterparty import (
    KIND_CHARACTER,
    KIND_CORPORATION,
    resolve_counterparties,
)
from eveonline.client import EsiResponse


class CounterpartyEsiNamesTest(TestCase):
    @patch("buyback.helpers.counterparty.EsiClient.resolve_universe_names")
    def test_unknown_ids_resolve_through_esi_in_chunks(self, names):
        def answer(chunk):
            return EsiResponse(
                0,
                data=[
                    {
                        "id": eid,
                        "name": f"N{eid}",
                        "category": (
                            "character" if eid % 2 else "corporation"
                        ),
                    }
                    for eid in chunk
                ],
            )

        names.side_effect = answer
        ids = list(range(1, 1502))

        resolved = resolve_counterparties(ids)

        self.assertEqual(names.call_count, 2)
        self.assertEqual(len(names.call_args_list[0].args[0]), 1000)
        self.assertEqual(len(names.call_args_list[1].args[0]), 501)
        self.assertEqual(len(resolved), 1501)
        self.assertEqual(resolved[3].name, "N3")
        self.assertEqual(resolved[3].kind, KIND_CHARACTER)
        self.assertEqual(resolved[4].kind, KIND_CORPORATION)

    @patch("buyback.helpers.counterparty.EsiClient.resolve_universe_names")
    def test_failed_lookup_falls_back_to_the_id(self, names):
        names.return_value = EsiResponse(404)
        resolved = resolve_counterparties([42])
        self.assertEqual(resolved[42].name, "42")
        self.assertEqual(resolved[42].kind, "")
