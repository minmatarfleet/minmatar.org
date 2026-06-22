"""Tests for corporation blueprint sync helpers."""

from unittest.mock import patch

import factory
from django.db.models import signals
from esi.models import Scope, Token

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.helpers.corporations.update import update_corporation_blueprints
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationBlueprint,
)
from eveonline.scopes import scopes_for, TokenType


def _blueprint_payload(item_id: int, *, type_id: int = 684) -> dict:
    return {
        "item_id": item_id,
        "type_id": type_id,
        "location_id": 60004600,
        "location_flag": "CorpSAG1",
        "material_efficiency": 10,
        "time_efficiency": 20,
        "quantity": -1,
        "runs": -1,
    }


class UpdateCorporationBlueprintsTestCase(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.corporations.update.EsiClient")
    def test_deduplicates_duplicate_esi_item_ids(self, esi_client_cls):
        corporation = EveCorporation.objects.create(
            corporation_id=98733885,
            name="Ballah Inc.",
        )
        token = Token.objects.create(character_id=90000001)
        for scope_name in scopes_for(TokenType.DIRECTOR):
            scope, _ = Scope.objects.get_or_create(name=scope_name)
            token.scopes.add(scope)
        ceo = EveCharacter.objects.create(
            character_id=token.character_id,
            token=token,
        )
        corporation.ceo = ceo
        corporation.save()

        duplicate_item_id = 1048554846970
        esi_client_cls.return_value.get_corporation_blueprints.return_value = (
            EsiResponse(
                response_code=200,
                data=[
                    _blueprint_payload(111565214),
                    _blueprint_payload(duplicate_item_id, type_id=100),
                    _blueprint_payload(duplicate_item_id, type_id=200),
                ],
            )
        )

        synced = update_corporation_blueprints(corporation.corporation_id)

        self.assertEqual(2, synced)
        self.assertEqual(
            2,
            EveCorporationBlueprint.objects.filter(
                corporation=corporation
            ).count(),
        )
        saved = EveCorporationBlueprint.objects.get(
            corporation=corporation,
            item_id=duplicate_item_id,
        )
        self.assertEqual(200, saved.type_id)
