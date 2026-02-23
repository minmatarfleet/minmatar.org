import logging
import uuid

from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from celery import chain, group

from app.celery import app
from discord.client import DiscordClient
from eveonline.client import EsiClient
from eveonline.models import (
    EveCharacterContract,
    EveCorporationContract,
    EveLocation,
)
from market.helpers import (
    clear_structure_sell_orders_for_location,
    create_or_update_contract,
    create_or_update_contract_from_db_contract,
    get_character_with_structure_markets_scope,
    process_structure_sell_orders_page,
    update_completed_contracts,
    update_expired_contracts,
    update_region_market_history_for_type,
)
from market.helpers.contract_fetch import (
    MARKET_ITEM_HISTORY_SPREAD_SECONDS,
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
def fetch_eve_market_contracts():
    start_time = timezone.now()
    logger.info("fetch_eve_market_contracts starting")

    EveMarketContractError.objects.all().delete()
    logger.info("Cleared previous contract errors")

    market_locations = list(EveLocation.objects.filter(market_active=True))
    location_ids = [loc.location_id for loc in market_locations]
    locations_by_id = {loc.location_id: loc for loc in market_locations}
    logger.info(
        "Loaded %s market-active location(s): %s",
        len(market_locations),
        [loc.location_name for loc in market_locations],
    )

    # 1. Fetch public contracts from ESI and store them
    logger.info("Step 1: Fetching public contracts from ESI")
    for location in market_locations:
        logger.info(
            "Fetching public contracts for %s (region_id=%s)",
            location.location_name,
            location.region_id,
        )
        if not location.region_id:
            logger.info(
                "Skipping contract update for location without region: %s",
                location.location_name,
            )
            continue
        esi_response = EsiClient(None).get_public_contracts(location.region_id)
        if not esi_response.success():
            logger.warning(
                "ESI error %s fetching public contracts for %s (region_id=%s)",
                esi_response.response_code,
                location.location_name,
                location.region_id,
            )
            continue
        contracts = list(esi_response.results())
        for contract in contracts:
            create_or_update_contract(contract, location)
        logger.info(
            "Processed %s public contract(s) for %s",
            len(contracts),
            location.location_name,
        )

    logger.info("Step 1 complete: public contracts from ESI updated")

    # Contract IDs already stored as finished (private) never change state; skip them
    finished_private_contract_ids = set(
        EveMarketContract.objects.filter(
            status="finished", is_public=False
        ).values_list("id", flat=True)
    )
    logger.info(
        "Excluding %s finished private contract ID(s) from character/corp sync",
        len(finished_private_contract_ids),
    )

    # 2. Fetch character contracts from our database, store if they match parameters
    logger.info("Step 2: Fetching character contracts from database")
    if not location_ids:
        logger.info("No market locations, skipping character contracts")
    else:
        char_contracts = EveCharacterContract.objects.filter(
            type=EveMarketContract.esi_contract_type,
            start_location_id__in=location_ids,
        ).exclude(contract_id__in=finished_private_contract_ids)
        char_contracts_list = list(char_contracts)
        logger.info(
            "Found %s character contract(s) to process",
            len(char_contracts_list),
        )
        char_stored = 0
        for db_contract in char_contracts_list:
            location = locations_by_id.get(db_contract.start_location_id)
            if location and create_or_update_contract_from_db_contract(
                db_contract, location
            ):
                char_stored += 1
        logger.info(
            "Step 2 complete: stored %s character contract(s) into EveMarketContract",
            char_stored,
        )

    # 3. Fetch corporation contracts from our database, store if they match parameters
    logger.info("Step 3: Fetching corporation contracts from database")
    if not location_ids:
        logger.info("No market locations, skipping corporation contracts")
    else:
        corp_contracts = EveCorporationContract.objects.filter(
            type=EveMarketContract.esi_contract_type,
            start_location_id__in=location_ids,
        ).exclude(contract_id__in=finished_private_contract_ids)
        corp_contracts_list = list(corp_contracts)
        logger.info(
            "Found %s corporation contract(s) to process",
            len(corp_contracts_list),
        )
        corp_stored = 0
        for db_contract in corp_contracts_list:
            location = locations_by_id.get(db_contract.start_location_id)
            if location and create_or_update_contract_from_db_contract(
                db_contract, location
            ):
                corp_stored += 1
        logger.info(
            "Step 3 complete: stored %s corporation contract(s) into EveMarketContract",
            corp_stored,
        )

    logger.info("Updating completed contract statuses (since %s)", start_time)
    update_completed_contracts(start_time)
    logger.info("Updating expired contract statuses (since %s)", start_time)
    update_expired_contracts(start_time)

    duration = (timezone.now() - start_time).total_seconds()
    logger.info("fetch_eve_market_contracts complete in %.1fs", duration)


@app.task()
def fetch_market_item_history_for_type(type_id: int) -> int:
    """
    Update EveMarketItemHistory for one type_id across all unique region_ids
    from market-active locations. Returns total history rows updated.
    """
    region_ids = list(
        EveLocation.objects.filter(prices_active=True, region_id__isnull=False)
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
