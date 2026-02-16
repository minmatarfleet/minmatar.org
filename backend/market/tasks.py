import logging
import uuid

from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from esi.models import Token

from celery import chain, group

from app.celery import app
from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import EveAlliance, EveCharacter, EveLocation
from market.helpers import (
    clear_structure_sell_orders_for_location,
    create_character_market_contracts,
    create_corporation_market_contracts,
    create_or_update_contract,
    get_character_with_structure_markets_scope,
    process_structure_sell_orders_page,
    update_completed_contracts,
    update_expired_contracts,
    update_region_market_history_for_type,
)
from market.helpers.contract_fetch import (
    CHARACTER_CONTRACT_SCOPES,
    CONTRACT_FETCH_SPREAD_SECONDS,
    MARKET_ITEM_HISTORY_SPREAD_SECONDS,
    alliance_corporation_ids,
    get_character_with_contract_scope_for_corporation,
    known_contract_issuer_ids,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractError,
    EveMarketItemOrder,
)

logger = logging.getLogger(__name__)

discord = DiscordClient()


@app.task()
def fetch_eve_character_contracts_for_character(character_id: int):
    """Fetch market contracts for a single character. Idempotent."""
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping contract fetch", character_id
        )
        return
    if character.esi_suspended:
        logger.info(
            "Not fetching character contracts for ESI suspended character %s",
            character_id,
        )
        return
    if not Token.get_token(character_id, CHARACTER_CONTRACT_SCOPES):
        logger.debug(
            "No valid token for character %s, skipping contract fetch",
            character_id,
        )
        return
    try:
        create_character_market_contracts(character_id)
    except Exception as e:
        logger.error(
            "Failed to fetch character contracts %s: %s",
            character_id,
            e,
        )


@app.task()
def fetch_eve_corporation_contracts_for_corporation(corporation_id: int):
    """Fetch market contracts for a single corporation. Idempotent."""
    character_id = get_character_with_contract_scope_for_corporation(
        corporation_id
    )
    if not character_id:
        logger.warning(
            "No character with contract scope for corporation %s, skipping",
            corporation_id,
        )
        return
    try:
        create_corporation_market_contracts(corporation_id, character_id)
    except Exception as e:
        logger.error(
            "Failed to fetch corporation contracts %s: %s",
            corporation_id,
            e,
        )


@app.task()
def fetch_eve_character_contracts():
    """
    Schedule per-character contract fetches for alliance characters,
    spread over CONTRACT_FETCH_SPREAD_SECONDS (4 hours).
    """
    alliance_ids = set(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    character_ids = list(
        EveCharacter.objects.exclude(token__isnull=True)
        .filter(alliance_id__in=alliance_ids)
        .values_list("character_id", flat=True)
    )
    for i, character_id in enumerate(character_ids):
        delay = i % CONTRACT_FETCH_SPREAD_SECONDS
        fetch_eve_character_contracts_for_character.apply_async(
            args=[character_id],
            countdown=delay,
        )
    logger.info(
        "Scheduled %s character contract fetches over %s hours",
        len(character_ids),
        CONTRACT_FETCH_SPREAD_SECONDS / 3600,
    )


@app.task()
def fetch_eve_corporation_contracts():
    """
    Schedule per-corporation contract fetches for alliance corporations,
    spread over CONTRACT_FETCH_SPREAD_SECONDS (4 hours).
    """
    corporation_ids = list(alliance_corporation_ids())
    for i, corporation_id in enumerate(corporation_ids):
        delay = i % CONTRACT_FETCH_SPREAD_SECONDS
        fetch_eve_corporation_contracts_for_corporation.apply_async(
            args=[corporation_id],
            countdown=delay,
        )
    logger.info(
        "Scheduled %s corporation contract fetches over %s hours",
        len(corporation_ids),
        CONTRACT_FETCH_SPREAD_SECONDS / 3600,
    )


@app.task()
def expire_unknown_eve_market_contracts():
    """
    Mark outstanding market contracts as expired when the issuer is not
    a known alliance character or corporation (or public).
    """
    known = known_contract_issuer_ids()
    updated = (
        EveMarketContract.objects.filter(status="outstanding")
        .exclude(
            Q(issuer_external_id__in=known)
            | Q(issuer_external_id__isnull=True)
        )
        .update(status="expired")
    )
    logger.info("Expired %s market contracts with unknown issuers", updated)


@app.task()
def clear_structure_sell_orders_for_location_task(
    location_id: int, task_uid: str
) -> int:
    """Celery task: delete sell orders for a structure that were not imported by task_uid."""
    return clear_structure_sell_orders_for_location(location_id, task_uid)


@app.task()
def process_structure_sell_orders_page_task(
    character_id: int, location_id: int, page: int, task_uid: str
) -> tuple[int, int]:
    """Celery task: fetch one page of structure market orders and insert sell orders."""
    orders_created, total_volume = process_structure_sell_orders_page(
        character_id, location_id, page, task_uid
    )
    logger.info(
        "Structure sell orders page task complete: location_id=%s page=%s "
        "orders_created=%s total_volume=%s",
        location_id,
        page,
        orders_created,
        total_volume,
    )
    return orders_created, total_volume


@app.task()
def spawn_structure_sell_orders_pages(
    _clear_result,  # pylint: disable=invalid-name
    character_id: int,
    location_id: int,
    total_pages: int,
    task_uid: str,
) -> None:
    """
    Spawn a task per page for a structure (chained after clear). Ignores
    _clear_result; runs the group of page tasks with the same task_uid.
    """
    page_tasks = group(
        process_structure_sell_orders_page_task.s(
            character_id, location_id, page, task_uid
        )
        for page in range(1, total_pages + 1)
    )
    page_tasks.apply_async()


@app.task()
def fetch_structure_sell_orders():
    """
    Fetch structure market sell orders for all market-active locations. Gets
    total pages from ESI (X-Pages), then for each structure fires: clear
    orders, then one task per page to fetch and insert (structure + page).
    Requires a character with esi-markets.structure_markets.v1 and docking
    access to each structure.
    """
    logger.info("Starting fetch_structure_sell_orders")

    character_id = get_character_with_structure_markets_scope()
    if not character_id:
        logger.warning(
            "No character with structure market scope, skipping structure sell orders"
        )
        return

    logger.info(
        "Using character_id=%s for structure market orders",
        character_id,
    )

    locations_list = list(EveLocation.objects.filter(market_active=True))
    if not locations_list:
        logger.info("No market-active locations configured, nothing to sync")
        return

    logger.info(
        "Scheduling structure sell orders for %s location(s): %s",
        len(locations_list),
        [loc.location_name for loc in locations_list],
    )

    client = EsiClient(character_id)
    scheduled = 0
    skipped = 0

    for location in locations_list:
        try:
            first_page_data, total_pages = (
                client.get_structure_market_orders_first_page_and_total(
                    location.location_id
                )
            )
        except Exception as e:
            logger.exception(
                "Failed to get page count for location %s: %s",
                location.location_name,
                e,
            )
            skipped += 1
            continue

        if total_pages < 1 or first_page_data is None:
            logger.warning(
                "No data or pages for location %s (total_pages=%s), skipping",
                location.location_name,
                total_pages,
            )
            skipped += 1
            continue

        task_uid = uuid.uuid4().hex
        chain(
            clear_structure_sell_orders_for_location_task.si(
                location.location_id, task_uid
            ),
            spawn_structure_sell_orders_pages.s(
                character_id,
                location.location_id,
                total_pages,
                task_uid,
            ),
        ).apply_async()
        scheduled += 1
        logger.info(
            "Scheduled location %s: %s page(s)",
            location.location_name,
            total_pages,
        )

    logger.info(
        "fetch_structure_sell_orders complete: %s scheduled, %s skipped",
        scheduled,
        skipped,
    )


def fetch_eve_market_transactions():
    pass


@app.task()
def notify_eve_market_contract_warnings():
    message = "The following contracts are understocked:\n"
    for expectation in EveMarketContractExpectation.objects.all():
        if expectation.is_understocked:
            message += f"**{expectation.fitting.name}** ({expectation.current_quantity}/{expectation.desired_quantity})\n"
    message += f"\n\n{settings.WEB_LINK_URL}/market/contracts/"

    discord.create_message(
        channel_id=settings.DISCORD_SUPPLY_CHANNEL_ID, message=message
    )


@app.task()
def fetch_eve_public_contracts():
    start_time = timezone.now()

    EveMarketContractError.objects.all().delete()

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
    update_expired_contracts(start_time)


@app.task()
def fetch_market_item_history_for_type(type_id: int) -> int:
    """
    Update EveMarketItemHistory for one type_id across all unique region_ids
    from market-active locations. Returns total history rows updated.
    """
    region_ids = list(
        EveLocation.objects.filter(market_active=True, region_id__isnull=False)
        .values_list("region_id", flat=True)
        .distinct()
    )
    if not region_ids:
        logger.debug("No regions for type_id=%s", type_id)
        return 0

    total_updated = 0
    for region_id in region_ids:
        updated, _ = update_region_market_history_for_type(region_id, type_id)
        total_updated += updated

    logger.info(
        "fetch_market_item_history_for_type type_id=%s regions=%s rows_updated=%s",
        type_id,
        len(region_ids),
        total_updated,
    )
    return total_updated


@app.task()
def fetch_market_item_history():
    """
    Fire a task per unique type_id we track in EveMarketItemOrder; each task
    processes that type_id across all unique location regions. Tasks are
    spread over MARKET_ITEM_HISTORY_SPREAD_SECONDS (4 hours).
    Runs daily.
    """
    logger.info("Starting fetch_market_item_history")

    type_ids = list(
        EveMarketItemOrder.objects.values_list("item_id", flat=True).distinct()
    )

    if not type_ids:
        logger.info("No item orders, skipping market item history")
        return

    for i, type_id in enumerate(type_ids):
        delay = i % MARKET_ITEM_HISTORY_SPREAD_SECONDS
        fetch_market_item_history_for_type.apply_async(
            args=[type_id],
            countdown=delay,
        )

    logger.info(
        "fetch_market_item_history scheduled %s type_id task(s) over %.0f hour(s)",
        len(type_ids),
        MARKET_ITEM_HISTORY_SPREAD_SECONDS / 3600,
    )
