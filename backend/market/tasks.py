import logging
from datetime import datetime

from django.db.models import Q
from django.utils import timezone
from esi.models import Token

from app.celery import app
from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from fittings.models import EveFitting
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.models import EveMarketContract, EveMarketContractExpectation

logger = logging.getLogger(__name__)

discord = DiscordClient()

NOTIFICATION_CHANNEL = 1174095138197340300


@app.task()
def fetch_eve_market_contracts():
    known_entity_ids = []
    characters = EveCharacter.objects.exclude(token__isnull=True)

    for character in characters:
        if character.esi_suspended:
            logger.info(
                f"Not fetching character contracts for ESI suspended character {character.character_id}"
            )
            continue
        required_scopes = ["esi-contracts.read_character_contracts.v1"]
        if not Token.get_token(character.character_id, required_scopes):
            continue

        logger.debug(f"Fetching character contracts {character.character_id}")
        try:
            create_character_market_contracts(character.character_id)
            known_entity_ids.append(character.character_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch character contracts {character.character_id}: {e}"
            )

    corporations = EveCorporation.objects.filter(
        alliance__name__in=[
            "Minmatar Fleet Alliance",
            "Minmatar Fleet Associates",
        ],
    ).distinct()

    for corporation in corporations:
        required_scopes = ["esi-contracts.read_corporation_contracts.v1"]
        if not Token.get_token(corporation.ceo.character_id, required_scopes):
            continue

        logger.info(
            f"Fetching corporation contracts {corporation.corporation_id}"
        )
        try:
            create_corporation_market_contracts(corporation.corporation_id)
            known_entity_ids.append(corporation.corporation_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch corporation contracts {corporation.corporation_id}: {e}"
            )

    # Expire any outstanding contracts that are not associated with known entities
    (
        EveMarketContract.objects.filter(status="outstanding")
        .exclude(
            Q(issuer_external_id__in=known_entity_ids)
            | Q(issuer_external_id__isnull=True)
        )
        .update(status="expired")
    )


def fetch_eve_market_orders():
    pass


def fetch_eve_market_transactions():
    pass


@app.task()
def notify_eve_market_contract_warnings():
    message = "The following contracts are understocked:\n"
    for expectation in EveMarketContractExpectation.objects.all():
        if expectation.is_understocked:
            message += f"**{expectation.fitting.name}** ({expectation.current_quantity}/{expectation.desired_quantity})\n"

    discord.create_message(channel_id=NOTIFICATION_CHANNEL, message=message)


@app.task()
def fetch_eve_public_contracts():
    start_time = timezone.now()

    logger.info("Fetching and updating public contracts")

    for location in EveLocation.objects.filter(market_active=True):
        logger.info("Fetching contracts for %s", location.location_name)
        if not location.region_id:
            logger.info(
                "Skipping contract update for location without region: %s",
                location.location_name,
            )
            continue
        esi_response = EsiClient(None).get_public_contracts(location.region_id)
        if not esi_response.success():
            logger.info(
                "Error %d fetching contracts for region: %d",
                esi_response.response_code,
                location.region_id,
            )
        for contract in esi_response.results():
            create_or_update_contract(contract, location)

    logger.info("Public contracts updated")

    update_completed_contracts(start_time)


def create_or_update_contract(esi_contract, location: EveLocation):
    if not esi_contract["type"] == EveMarketContract.esi_contract_type:
        return
    if not esi_contract["start_location_id"] == location.location_id:
        return
    if esi_contract["date_expired"] <= timezone.now():
        return

    fitting = get_fitting_for_contract(esi_contract["title"])
    if not fitting:
        logger.info(
            "Ignoring public contract %d, unknown fitting: %s",
            esi_contract["contract_id"],
            esi_contract["title"],
        )
        return

    if esi_contract["status"] == "outstanding":
        status = "outstanding"
    elif esi_contract["status"] == "finished":
        status = "finished"
    else:
        status = "expired"

    contract, _ = EveMarketContract.objects.get_or_create(
        id=esi_contract["contract_id"],
        defaults={
            "price": esi_contract["price"],
            "issuer_external_id": esi_contract["issuer_id"],
        },
    )
    contract.title = esi_contract["title"]
    contract.status = status
    contract.assignee_id = esi_contract["assignee_id"]
    contract.acceptor_id = esi_contract["acceptor_id"]
    contract.expires_at = esi_contract["date_expired"]
    contract.fitting = fitting
    contract.location = location
    contract.is_public = True
    contract.last_updated = timezone.now()
    contract.save()


fitting_cache = {}


def get_fitting_for_contract(contract_summary: str) -> EveFitting | None:
    if contract_summary is None or contract_summary.strip() == "":
        return None

    if contract_summary in fitting_cache:
        return fitting_cache[contract_summary]

    contract_summary = contract_summary.replace("[FLEET]", "[FL33T]")

    fitting = None

    possible_matches = EveFitting.objects.filter(
        Q(name__iexact=contract_summary)
        | Q(aliases__contains=contract_summary)
    )

    for candidate in possible_matches:
        if candidate.name.lower() == contract_summary.lower():
            fitting = candidate
            break
        for alias in candidate.aliases.lower().split(","):
            if alias == contract_summary.lower():
                fitting = candidate
                break

    if not fitting:
        return None

    fitting_cache[contract_summary] = fitting
    return fitting


def update_completed_contracts(cutoff: datetime):
    updated = (
        EveMarketContract.objects.filter(expires_at__lt=cutoff)
        .filter(status="outstanding")
        .update(status="expired")
    )
    logger.info("Set %d public contracts to expired status", updated)
