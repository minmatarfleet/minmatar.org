import logging
from datetime import datetime, timedelta
from random import randint

from django.contrib.auth.models import User
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveType
from pydantic import BaseModel

from eveonline.models import EveCharacter, EvePrimaryCharacter
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from reminders.messages.rat_quotes import rat_quotes
from srp.srp_table import reimbursement_class_lookup, reimbursement_ship_lookup

from .models import EveFleetShipReimbursement

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


def recalculate_reimbursement_amount(reimbursement: EveFleetShipReimbursement):
    """
    Recalculate the amount for the ship
    """
    ship_type, _ = EveType.objects.get_or_create_esi(
        id=reimbursement.ship_type_id
    )
    reimbursement.amount = get_reimbursement_amount(ship_type)
    reimbursement.save()


def is_valid_for_reimbursement(killmail: KillmailDetails, fleet: EveFleet):
    """
    Check if a character is valid for reimbursement
    """

    if not EveFleetInstance.objects.filter(
        eve_fleet=fleet,
    ).exists():
        return True, "Non-fleet SRP"

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

    if fleet_instance.end_time and (
        fleet_instance.end_time + timedelta(hours=2) < killmail.timestamp
    ):
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
    mail_body = f"Your SRP request for fleet {reimbursement.fleet.id} ({reimbursement.ship_name}) has been {reimbursement.status}."
    if reimbursement.status == "approved":
        mail_body += f" You have been reimbursed {reimbursement.amount} ISK."

    # get random rat quote
    rat_quote_index = randint(0, len(rat_quotes) - 1)
    rat_quote = rat_quotes[rat_quote_index]

    mail_body += f"\n\n\n{rat_quote}\n\n\n"

    mail_body += "Best,\nMr. ThatCares"

    token = Token.objects.filter(
        character_id=mail_character_id, scopes__name="esi-mail.send_mail.v1"
    ).first()
    if not token:
        logger.error("Missing token for mail")
        return

    result = esi.client.Mail.post_characters_character_id_mail(
        mail={
            "subject": mail_subject,
            "body": mail_body,
            "recipients": [
                {
                    "recipient_id": reimbursement.primary_character_id,
                    "recipient_type": "character",
                }
            ],
        },
        character_id=mail_character_id,
        token=token.valid_access_token(),
    ).result()

    logger.info(
        f"Mail sent to {reimbursement.primary_character_id} for reimbursement"
    )
    return result
