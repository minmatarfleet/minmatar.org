"""
Activity processors: scan source models and create TribeGroupActivityRecord rows
for tribe members when their activity matches an active TribeGroupActivity config.
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from datetime import datetime as dt_datetime, time as dt_time

from eveonline.models import (
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCharacterMiningEntry,
    EveCorporationContract,
    EveCorporationWalletJournalEntry,
)
from fleets.models import EveFleet, EveFleetInstanceMember
from industry.models import IndustryOrderItemAssignment
from market.models import EveMarketItemTransaction

from tribes.models import (
    TribeGroupActivity,
    TribeGroupActivityRecord,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)


def _get_member_characters(activity):
    """
    Return list of (character, user) for all characters currently committed to
    an active membership in the activity's tribe group.
    """
    memberships = TribeGroupMembership.objects.filter(
        tribe_group=activity.tribe_group,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).values_list("id", "user_id")
    membership_ids = [m[0] for m in memberships]

    commitments = TribeGroupMembershipCharacter.objects.filter(
        membership_id__in=membership_ids
    ).select_related("character", "membership")

    return [
        (c.character, c.membership.user)
        for c in commitments
        if c.character_id and c.membership.user_id
    ]


def _create_record(
    activity,
    reference_type,
    reference_id,
    character=None,
    user=None,
    source_type_id=None,
    target_type_id=None,
    quantity=None,
    unit="",
    occurred_at=None,
):
    """Create a TribeGroupActivityRecord if one does not exist (dedupe by ref)."""
    defaults = {
        "character": character,
        "user": user,
        "source_type_id": source_type_id,
        "target_type_id": target_type_id,
        "quantity": quantity,
        "unit": unit or "",
        "occurred_at": occurred_at,
    }
    _, created = TribeGroupActivityRecord.objects.get_or_create(
        tribe_group_activity=activity,
        reference_type=reference_type,
        reference_id=reference_id,
        defaults=defaults,
    )
    return created


def _datetime_from_date(d):
    if d is None:
        return None
    return timezone.make_aware(dt_datetime.combine(d, dt_time.min))


# ---------------------------------------------------------------------------
# Per-activity-type processors (each returns count of new records created)
# ---------------------------------------------------------------------------


def process_killmail(activity):
    """Kills: member was attacker. source = attacker ship, target = victim ship."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_eve_ids = {c.character_id for c, _ in members}
    char_by_eve_id = {c.character_id: c for c, _ in members}
    user_by_eve_id = {c.character_id: u for c, u in members}

    attacker_qs = EveCharacterKillmailAttacker.objects.filter(
        character_id__in=char_eve_ids,
    ).select_related("killmail")

    if activity.source_eve_type_id is not None:
        attacker_qs = attacker_qs.filter(
            ship_type_id=activity.source_eve_type_id
        )

    if activity.target_eve_type_id is not None:
        attacker_qs = attacker_qs.filter(
            killmail__ship_type_id=activity.target_eve_type_id
        )

    created = 0
    for att in attacker_qs:
        killmail = att.killmail
        if killmail.victim_character_id == att.character_id:
            continue
        character = char_by_eve_id.get(att.character_id)
        if not character:
            continue
        ref_id = f"{killmail.pk}-{att.character_id}"
        if _create_record(
            activity,
            "EveCharacterKillmail",
            ref_id,
            character=character,
            user=user_by_eve_id.get(att.character_id),
            source_type_id=att.ship_type_id,
            target_type_id=killmail.ship_type_id,
            occurred_at=killmail.killmail_time,
        ):
            created += 1
    return created


def process_lossmail(activity):
    """Losses: member was victim. source = victim ship (the one they lost)."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    # EveCharacterKillmail.character_id is FK to EveCharacter (Django pk), not EVE character_id
    char_pks = {c.id for c, _ in members}
    char_user = {c.id: u for c, u in members}

    qs = EveCharacterKillmail.objects.filter(
        character_id__in=char_pks,
        victim_character_id=F("character__character_id"),
    ).select_related("character")

    if activity.source_eve_type_id is not None:
        qs = qs.filter(ship_type_id=activity.source_eve_type_id)

    created = 0
    for killmail in qs:
        if _create_record(
            activity,
            "EveCharacterKillmail",
            str(killmail.pk),
            character=killmail.character,
            user=char_user.get(killmail.character_id),
            source_type_id=killmail.ship_type_id,
            target_type_id=None,
            occurred_at=killmail.killmail_time,
        ):
            created += 1
    return created


def process_fleet_participation(activity):
    """Fleet instance members: match by character_id (bare int)."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = {c.character_id for c, _ in members}
    # Resolve character_id -> (EveCharacter, User) for records
    char_to_pair = {c.character_id: (c, u) for c, u in members}

    qs = EveFleetInstanceMember.objects.filter(character_id__in=char_ids)
    if activity.source_eve_type_id is not None:
        qs = qs.filter(ship_type_id=activity.source_eve_type_id)

    created = 0
    for member in qs:
        pair = char_to_pair.get(member.character_id)
        if not pair:
            continue
        character, user = pair
        if _create_record(
            activity,
            "EveFleetInstanceMember",
            str(member.pk),
            character=character,
            user=user,
            source_type_id=member.ship_type_id,
            target_type_id=None,
            occurred_at=member.join_time,
        ):
            created += 1
    return created


def process_mining(activity):
    """Mining ledger: one row per (character, eve_type, date, solar_system). Quantity in m³ for leaderboard summing."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = [c.id for c, _ in members]
    char_user = {c.id: u for c, u in members}

    qs = EveCharacterMiningEntry.objects.filter(
        character_id__in=char_ids
    ).select_related("character", "eve_type")
    if activity.source_eve_type_id is not None:
        qs = qs.filter(eve_type_id=activity.source_eve_type_id)

    created = 0
    for entry in qs:
        ref_id = f"{entry.character_id}-{entry.eve_type_id}-{entry.date}-{entry.solar_system_id}"
        # Store quantity in m³ (units * volume per unit) for consistent leaderboard summing
        volume_per_unit = (
            float(entry.eve_type.volume)
            if entry.eve_type and entry.eve_type.volume is not None
            else 0.0
        )
        quantity_m3 = float(entry.quantity) * volume_per_unit
        if _create_record(
            activity,
            "EveCharacterMiningEntry",
            ref_id,
            character=entry.character,
            user=char_user.get(entry.character_id),
            source_type_id=entry.eve_type_id,
            target_type_id=None,
            quantity=quantity_m3,
            unit="m3",
            occurred_at=_datetime_from_date(entry.date),
        ):
            created += 1
    return created


def process_planetary_interaction(activity):
    """PI tax: corp wallet journal entries; character = first_party_id."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = {c.character_id for c, _ in members}
    char_by_id = {c.character_id: c for c, _ in members}
    user_by_char_id = {c.character_id: u for c, u in members}

    qs = EveCorporationWalletJournalEntry.objects.filter(
        ref_type__in=["planetary_export_tax", "planetary_import_tax"],
        first_party_id__in=char_ids,
    )

    created = 0
    for entry in qs:
        character = char_by_id.get(entry.first_party_id)
        if not character:
            continue
        amount = float(entry.amount) if entry.amount is not None else 0
        ref_id = f"{entry.corporation_id}-{entry.division}-{entry.ref_id}"
        if _create_record(
            activity,
            "EveCorporationWalletJournalEntry",
            ref_id,
            character=character,
            user=user_by_char_id.get(entry.first_party_id),
            source_type_id=None,
            target_type_id=None,
            quantity=amount,
            unit="ISK",
            occurred_at=entry.date,
        ):
            created += 1
    return created


def process_industry(activity):
    """Industry jobs: status=delivered. When source_eve_type_id is set (blueprint type), only those jobs are recorded."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = [c.id for c, _ in members]
    char_user = {c.id: u for c, u in members}

    qs = EveCharacterIndustryJob.objects.filter(
        character_id__in=char_ids,
        status="delivered",
    )
    # Respect config: filter by blueprint type when set (e.g. specific ship or module blueprint)
    if activity.source_eve_type_id is not None:
        qs = qs.filter(blueprint_type_id=activity.source_eve_type_id)

    created = 0
    for job in qs:
        if _create_record(
            activity,
            "EveCharacterIndustryJob",
            str(job.job_id),
            character=job.character,
            user=char_user.get(job.character_id),
            source_type_id=job.blueprint_type_id,
            target_type_id=None,
            quantity=float(job.runs),
            unit="runs",
            occurred_at=job.end_date,
        ):
            created += 1
    return created


def process_contract(activity):
    """Contracts posted by member (issuer_id)."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = {c.character_id for c, _ in members}
    char_by_id = {c.character_id: c for c, _ in members}
    user_by_char_id = {c.character_id: u for c, u in members}

    qs = EveCharacterContract.objects.filter(issuer_id__in=char_ids)

    created = 0
    for contract in qs:
        character = char_by_id.get(contract.issuer_id)
        if not character:
            continue
        price = float(contract.price) if contract.price is not None else 0
        if _create_record(
            activity,
            "EveCharacterContract",
            str(contract.contract_id),
            character=character,
            user=user_by_char_id.get(contract.issuer_id),
            source_type_id=None,
            target_type_id=None,
            quantity=price,
            unit="ISK",
            occurred_at=contract.date_completed or contract.date_issued,
        ):
            created += 1
    return created


def process_courier_contract(activity):
    """Courier deliveries: character contracts (acceptor) + corp contracts (acceptor)."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = {c.character_id for c, _ in members}
    char_by_id = {c.character_id: c for c, _ in members}
    user_by_char_id = {c.character_id: u for c, u in members}

    created = 0

    # Character-level: contracts where this character is the acceptor
    char_contracts = EveCharacterContract.objects.filter(
        type="courier",
        status="finished",
        acceptor_id__in=char_ids,
    )
    for contract in char_contracts:
        character = char_by_id.get(contract.acceptor_id)
        if not character:
            continue
        volume = float(contract.volume) if contract.volume is not None else 0
        if _create_record(
            activity,
            "EveCharacterContract",
            str(contract.contract_id),
            character=character,
            user=user_by_char_id.get(contract.acceptor_id),
            source_type_id=None,
            target_type_id=None,
            quantity=volume,
            unit="m3",
            occurred_at=contract.date_completed or contract.date_accepted,
        ):
            created += 1

    # Corp-level: acceptor_id is bare int
    corp_contracts = EveCorporationContract.objects.filter(
        type="courier",
        status="finished",
        for_corporation=True,
        acceptor_id__in=char_ids,
    )
    for contract in corp_contracts:
        character = char_by_id.get(contract.acceptor_id)
        if not character:
            continue
        volume = float(contract.volume) if contract.volume is not None else 0
        ref_id = f"corp-{contract.contract_id}"
        if _create_record(
            activity,
            "EveCorporationContract",
            ref_id,
            character=character,
            user=user_by_char_id.get(contract.acceptor_id),
            source_type_id=None,
            target_type_id=None,
            quantity=volume,
            unit="m3",
            occurred_at=contract.date_completed or contract.date_accepted,
        ):
            created += 1

    return created


def process_market_order(activity):
    """Market sell transactions: issuer_external_id = character_id."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_ids = {c.character_id for c, _ in members}
    char_by_id = {c.character_id: c for c, _ in members}
    user_by_char_id = {c.character_id: u for c, u in members}

    qs = EveMarketItemTransaction.objects.filter(
        issuer_external_id__in=char_ids
    )
    if activity.source_eve_type_id is not None:
        qs = qs.filter(item_id=activity.source_eve_type_id)

    created = 0
    for txn in qs:
        character = char_by_id.get(txn.issuer_external_id)
        if not character:
            continue
        isk_value = (
            float(txn.price * txn.quantity)
            if txn.price and txn.quantity
            else 0
        )
        ref_id = str(txn.pk)
        if _create_record(
            activity,
            "EveMarketItemTransaction",
            ref_id,
            character=character,
            user=user_by_char_id.get(txn.issuer_external_id),
            source_type_id=txn.item_id,
            target_type_id=None,
            quantity=isk_value,
            unit="ISK",
            occurred_at=txn.sell_date,
        ):
            created += 1
    return created


def process_industry_order(activity):
    """Delivered industry order assignments tagged to this tribe group."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    char_pks = [c.id for c, _ in members]
    char_user = {c.id: u for c, u in members}

    qs = IndustryOrderItemAssignment.objects.filter(
        character_id__in=char_pks,
        order_item__order__tribe_groups=activity.tribe_group,
        delivered_at__isnull=False,
    ).select_related("order_item", "order_item__order", "character")

    if activity.source_eve_type_id is not None:
        qs = qs.filter(order_item__eve_type_id=activity.source_eve_type_id)

    created = 0
    for assignment in qs:
        occurred_at = (
            assignment.delivered_at or assignment.order_item.order.fulfilled_at
        )
        if _create_record(
            activity,
            "IndustryOrderItemAssignment",
            str(assignment.pk),
            character=assignment.character,
            user=char_user.get(assignment.character_id),
            source_type_id=assignment.order_item.eve_type_id,
            target_type_id=None,
            quantity=float(assignment.quantity),
            unit="units",
            occurred_at=occurred_at,
        ):
            created += 1
    return created


def process_fleet_commanded(activity):
    """Fleets led by roster members (created_by), excluding cancelled."""
    members = _get_member_characters(activity)
    if not members:
        return 0

    user_ids = {u.id for _, u in members}
    user_by_id = {u.id: u for _, u in members}

    qs = EveFleet.objects.filter(
        created_by_id__in=user_ids,
    ).exclude(status="cancelled")

    created = 0
    for fleet in qs:
        user = user_by_id.get(fleet.created_by_id)
        if not user:
            continue
        if _create_record(
            activity,
            "EveFleet",
            str(fleet.pk),
            character=None,
            user=user,
            source_type_id=None,
            target_type_id=None,
            occurred_at=fleet.start_time,
        ):
            created += 1
    return created


PROCESSORS = {
    TribeGroupActivity.KILLMAIL: process_killmail,
    TribeGroupActivity.LOSSMAIL: process_lossmail,
    TribeGroupActivity.FLEET_PARTICIPATION: process_fleet_participation,
    TribeGroupActivity.FLEET_COMMANDED: process_fleet_commanded,
    TribeGroupActivity.MINING: process_mining,
    TribeGroupActivity.PLANETARY_INTERACTION: process_planetary_interaction,
    TribeGroupActivity.INDUSTRY: process_industry,
    TribeGroupActivity.INDUSTRY_ORDER: process_industry_order,
    TribeGroupActivity.CONTRACT: process_contract,
    TribeGroupActivity.COURIER_CONTRACT: process_courier_contract,
    TribeGroupActivity.MARKET_ORDER: process_market_order,
}


def process_activity(activity):
    """Run the processor for this activity config; return count of new records."""
    if not activity.is_active:
        return 0
    processor = PROCESSORS.get(activity.activity_type)
    if not processor:
        return 0
    with transaction.atomic():
        return processor(activity)


def process_all_for_tribe_group(tribe_group):
    """Process all active TribeGroupActivity configs for this group; return total new records."""
    activities = TribeGroupActivity.objects.filter(
        tribe_group=tribe_group,
        is_active=True,
    )
    total = 0
    for activity in activities:
        total += process_activity(activity)
    return total
