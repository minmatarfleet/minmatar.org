"""Backfill occurred_at on TribeGroupActivityRecord from source models."""

from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from eveonline.models import (
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterMiningEntry,
    EveCorporationContract,
    EveCorporationWalletJournalEntry,
)
from fleets.models import EveFleet, EveFleetInstanceMember
from industry.models import IndustryOrderItemAssignment
from market.models import EveMarketItemTransaction

from tribes.models import TribeGroupActivityRecord


def _datetime_from_date(d):
    if d is None:
        return None
    return timezone.make_aware(datetime.combine(d, time.min))


def _occurred_at_killmail(ref_id):
    km_pk = ref_id.split("-", 1)[0] if "-" in ref_id else ref_id
    km = EveCharacterKillmail.objects.filter(pk=km_pk).first()
    return km.killmail_time if km else None


def _occurred_at_mining(ref_id):
    parts = ref_id.split("-")
    if len(parts) < 4:
        return None
    char_pk, type_id, date_str = parts[0], parts[1], parts[2]
    entry = EveCharacterMiningEntry.objects.filter(
        character_id=char_pk,
        eve_type_id=type_id,
        date=date_str,
    ).first()
    return _datetime_from_date(entry.date) if entry else None


def _occurred_at_wallet_journal(ref_id):
    parts = ref_id.split("-", 2)
    if len(parts) != 3:
        return None
    corp_id, division, journal_ref = parts
    entry = EveCorporationWalletJournalEntry.objects.filter(
        corporation_id=corp_id,
        division=division,
        ref_id=journal_ref,
    ).first()
    return entry.date if entry else None


def _occurred_at_industry_job(ref_id):
    job = EveCharacterIndustryJob.objects.filter(job_id=ref_id).first()
    return job.end_date if job else None


def _occurred_at_character_contract(ref_id):
    contract = EveCharacterContract.objects.filter(contract_id=ref_id).first()
    if not contract:
        return None
    return contract.date_completed or contract.date_issued


def _occurred_at_corp_contract(ref_id):
    contract_id = ref_id.replace("corp-", "", 1)
    contract = EveCorporationContract.objects.filter(
        contract_id=contract_id
    ).first()
    if not contract:
        return None
    return contract.date_completed or contract.date_accepted


def _occurred_at_market_txn(ref_id):
    txn = EveMarketItemTransaction.objects.filter(pk=ref_id).first()
    return txn.sell_date if txn else None


def _occurred_at_fleet_member(ref_id):
    member = EveFleetInstanceMember.objects.filter(pk=ref_id).first()
    return member.join_time if member else None


def _occurred_at_industry_assignment(ref_id):
    assignment = IndustryOrderItemAssignment.objects.filter(pk=ref_id).first()
    if not assignment:
        return None
    return assignment.delivered_at or assignment.order_item.order.fulfilled_at


def _occurred_at_fleet(ref_id):
    fleet = EveFleet.objects.filter(pk=ref_id).first()
    return fleet.start_time if fleet else None


_OCCURRED_AT_HANDLERS = {
    "EveCharacterKillmail": _occurred_at_killmail,
    "EveCharacterMiningEntry": _occurred_at_mining,
    "EveCorporationWalletJournalEntry": _occurred_at_wallet_journal,
    "EveCharacterIndustryJob": _occurred_at_industry_job,
    "EveCharacterContract": _occurred_at_character_contract,
    "EveCorporationContract": _occurred_at_corp_contract,
    "EveMarketItemTransaction": _occurred_at_market_txn,
    "EveFleetInstanceMember": _occurred_at_fleet_member,
    "IndustryOrderItemAssignment": _occurred_at_industry_assignment,
    "EveFleet": _occurred_at_fleet,
}


def _occurred_at_for_record(record):
    handler = _OCCURRED_AT_HANDLERS.get(record.reference_type)
    if not handler:
        return None
    return handler(record.reference_id)


class Command(BaseCommand):
    help = "Backfill TribeGroupActivityRecord.occurred_at from source event times."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts without saving.",
        )

    def handle(self, *args, **options):
        qs = TribeGroupActivityRecord.objects.filter(occurred_at__isnull=True)
        total = qs.count()
        updated = 0
        self.stdout.write(f"Records missing occurred_at: {total}")

        for record in qs.iterator():
            occurred_at = _occurred_at_for_record(record)
            if not occurred_at:
                continue
            if options["dry_run"]:
                updated += 1
                continue
            TribeGroupActivityRecord.objects.filter(pk=record.pk).update(
                occurred_at=occurred_at
            )
            updated += 1

        action = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(f"{action} {updated} record(s).")
