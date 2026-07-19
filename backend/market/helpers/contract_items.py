import logging

from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_CONTRACTS,
    get_director_with_scope,
)
from eveonline.models import (
    EveCharacterContract,
    EveCorporationContract,
)

from market.helpers.contract_match import (
    content_match_candidates,
    is_match_accepted,
    match_contract_to_fitting,
    normalize_contract_items,
)
from market.models import EveMarketContract, EveMarketContractItem

logger = logging.getLogger(__name__)


def store_contract_items(
    contract: EveMarketContract, raw_items: list[dict]
) -> dict[int, int]:
    EveMarketContractItem.objects.filter(contract=contract).delete()
    rows = []
    for row in raw_items:
        rows.append(
            EveMarketContractItem(
                contract=contract,
                type_id=row["type_id"],
                quantity=row.get("quantity", 1) or 1,
                is_included=bool(row.get("is_included", True)),
                is_singleton=row.get("is_singleton"),
            )
        )
    if rows:
        EveMarketContractItem.objects.bulk_create(rows)
    contract.items_fetched = True
    contract.items_fetched_at = timezone.now()
    contract.save(update_fields=["items_fetched", "items_fetched_at"])
    return normalize_contract_items(raw_items)


def apply_content_match(
    contract: EveMarketContract, contract_items: dict[int, int]
):
    """
    Persist the highest-% market-relevant fit and freeze via items_fetched.

    Works with or without a title match: wrong/missing titles still assign a
    fitting when module-weighted coverage is >= MATCH_THRESHOLD. Below
    threshold: clear fitting but keep match_score for admin attention.
    """
    preferred = contract.fitting
    candidates = content_match_candidates(contract, contract_items)
    if not candidates and preferred:
        candidates = [preferred]

    fitting, score, missing, extra = match_contract_to_fitting(
        contract_items,
        candidates,
        preferred_fitting=preferred,
    )
    contract.match_score = score
    contract.match_is_flagged = bool(score < 1.0) if score else True
    if fitting and is_match_accepted(score):
        contract.fitting = fitting
    else:
        contract.fitting = None
    contract.save(update_fields=["fitting", "match_score", "match_is_flagged"])
    return fitting, score, missing, extra


def fetch_public_contract_items(contract_id: int) -> tuple[bool, list[dict]]:
    response = EsiClient(None).get_public_contract_items(contract_id)
    if not response.success():
        logger.warning(
            "Failed to fetch public contract items %s: %s",
            contract_id,
            response.response_code,
        )
        return False, []
    return True, response.results() or []


def fetch_private_contract_items(
    contract: EveMarketContract,
) -> tuple[bool, list[dict]]:
    char_contract = (
        EveCharacterContract.objects.filter(contract_id=contract.pk)
        .select_related("character")
        .first()
    )
    if char_contract and char_contract.character:
        response = EsiClient(
            char_contract.character
        ).get_character_contract_items(contract.pk)
        if response.success():
            return True, response.results() or []

    corp_contract = (
        EveCorporationContract.objects.filter(contract_id=contract.pk)
        .select_related("corporation")
        .first()
    )
    if corp_contract and corp_contract.corporation:
        character = get_director_with_scope(
            corp_contract.corporation, SCOPE_CORPORATION_CONTRACTS
        )
        if character:
            response = EsiClient(character).get_corporation_contract_items(
                corp_contract.corporation.corporation_id,
                contract.pk,
            )
            if response.success():
                return True, response.results() or []
        else:
            logger.warning(
                "No director with corporation contracts scope for corp %s "
                "(contract %s)",
                corp_contract.corporation.corporation_id,
                contract.pk,
            )
    return False, []


def fetch_and_match_contract_items(contract_id: int) -> bool:
    contract = EveMarketContract.objects.filter(pk=contract_id).first()
    if not contract or contract.items_fetched:
        return False

    if contract.is_public:
        fetched, raw_items = fetch_public_contract_items(contract_id)
    else:
        fetched, raw_items = fetch_private_contract_items(contract)

    if not fetched:
        return False

    aggregated = store_contract_items(contract, raw_items)
    apply_content_match(contract, aggregated)
    return True
