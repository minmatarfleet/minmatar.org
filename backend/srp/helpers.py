from datetime import datetime, timedelta

from django.contrib.auth.models import User
from esi.clients import EsiClientProvider
from eveuniverse.models import EveType
from pydantic import BaseModel

from eveonline.models import EveCharacter, EvePrimaryCharacter
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from srp.srp_table import (
    reimbursement_class_lookup,
    reimbursement_ship_lookup,
)

from .models import EveFleetShipReimbursement
import logging

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


class KillmailDetails(BaseModel):
    timestamp: datetime
    killmail_id: int
    victim_character: EveCharacter
    victim_primary_character: EveCharacter
    ship: EveType

    class Config:
        arbitrary_types_allowed = True


class CharacterDoesNotExist(Exception):
    pass


class PrimaryCharacterDoesNotExist(Exception):
    pass


class UserCharacterMismatch(Exception):
    pass


def get_killmail_details(external_link: str, user: User):
    """
    Get details of a killmail
    """
    # https://esi.evetech.net/v1/killmails/122700189/95c87afb0ce8399e0c2d9b3d7a51936ea722d491/?datasource=tranquility
    killmail_id = external_link.split("/")[5]
    killmail_hash = external_link.split("/")[6]
    result = esi.client.Killmails.get_killmails_killmail_id_killmail_hash(
        killmail_id=killmail_id, killmail_hash=killmail_hash
    ).result()
    character_id = result["victim"]["character_id"]
    ship_type_id = result["victim"]["ship_type_id"]
    ship_type, _ = EveType.objects.get_or_create_esi(id=ship_type_id)

    if not EvePrimaryCharacter.objects.filter(
        character__token__user=user
    ).exists():
        raise PrimaryCharacterDoesNotExist("Primary character does not exist")
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        raise CharacterDoesNotExist("Character does not exist")
    if not EveCharacter.objects.filter(
        character_id=character_id, token__user=user
    ).exists():
        raise UserCharacterMismatch("Character does not belong to user")

    character = EveCharacter.objects.get(character_id=character_id)
    primary_character = EvePrimaryCharacter.objects.get(
        character__token__user=user
    ).character
    return KillmailDetails(
        killmail_id=killmail_id,
        victim_character=character,
        victim_primary_character=primary_character,
        ship=ship_type,
        timestamp=result["killmail_time"],
    )


def get_reimbursement_amount(ship: EveType):
    """
    Get the reimbursement amount for a ship
    """
    if ship.name in reimbursement_ship_lookup:
        return reimbursement_ship_lookup[ship.name]
    if ship.eve_group.name in reimbursement_class_lookup:
        return reimbursement_class_lookup[ship.eve_group.name]
    return 0


def is_valid_for_reimbursement(killmail: KillmailDetails, fleet: EveFleet):
    """
    Check if a character is valid for reimbursement
    """

    if not EveFleetInstance.objects.filter(
        eve_fleet=fleet,
    ).exists():
        logger.info(
            f"Killmail {killmail.killmail_id} not eligible for SRP, no fleet instance"
        )
        return False, "No fleet instance"

    fleet_instance = EveFleetInstance.objects.get(
        eve_fleet=fleet,
    )

    if not EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=fleet_instance,
        character_id=killmail.victim_character.character_id,
    ).exists():
        logger.info(
            f"Killmail {killmail.killmail_id} not eligible for SRP, character not in fleet"
        )
        return False, "Character not in fleet"

    if fleet_instance.end_time is None:
        logger.info(
            f"Killmail {killmail.killmail_id} not eligible for SRP, fleet not finished"
        )
        return False, "Fleet not finished"

    if fleet_instance.end_time + timedelta(hours=2) < killmail.timestamp:
        logger.info(
            f"Killmail {killmail.killmail_id} not eligible for SRP, lost after fleet ended"
        )
        return False, "Lost after fleet ended"

    if fleet_instance.start_time - timedelta(hours=1) > killmail.timestamp:
        logger.info(
            f"Killmail {killmail.killmail_id} not eligible for SRP, lost before fleet started"
        )
        return False, "Lost before fleet started"

    return True, None


def send_decision_notification(reimbursement: EveFleetShipReimbursement):
    mail_character_id = 2116116149
    mail_subject = "SRP Reimbursement Decision"
    mail_body = f"Your SRP request for fleet {reimbursement.fleet.id} has been {reimbursement.status}.\n"
    if reimbursement.status == "approved":
        mail_body += f" You have been reimbursed {reimbursement.amount} ISK."

    mail_body += "\nBest,\nMr. ThatCares"

    esi.client.Mail.send_mail(
        character_id=mail_character_id,
        subject=mail_subject,
        body=mail_body,
        recipients=[
            {
                "recipient_id": reimbursement.primary_character_id,
                "recipient_type": "character",
            }
        ],
    )
