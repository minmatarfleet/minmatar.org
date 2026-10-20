"""Turn investigation evidence into suggested affiliations.

A pet is a group that leans on a bigger one: most of its kills have the
partner on them, month after month, while the partner does plenty without
it, and the two never shoot each other. Two groups that lean on each other
about equally are allies; the smaller joins the bigger one's bloc. An
associate is a character outside a bloc who keeps turning up on its kills.

Scoring only suggests. Confirmed rows keep their relation and status,
rejected rows are never touched, and manual rows only get fresh evidence.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.db.models import Count, Max, Min, Sum
from django.utils import timezone

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveCharacter
from intel.affiliations import resolve
from intel.affiliations.constants import (
    ASSOCIATE_MONTHS,
    ASSOCIATE_SHARED,
    ENDED_AFTER_MONTHS,
    MAX_AGAINST_FLOOR,
    MAX_AGAINST_SHARE,
    MILITIA_SHARE,
    MIN_KILLS,
    MIN_MONTHS_TOGETHER,
    PARTNER_PRIORITY,
    PET_ASYMMETRY,
    PET_SHARE,
    QUEUE_TOP_PARTNERS,
    RECENT_MONTHS,
    WINDOW_MONTHS,
)
from intel.affiliations.investigate import month_starts
from intel.affiliations.names import names_for
from intel.models import (
    IntelAffiliation,
    IntelBloc,
    IntelCoAttack,
    IntelEntity,
    IntelSampleMonth,
)

logger = logging.getLogger(__name__)

Kind = IntelEntity.Kind
Relation = IntelAffiliation.Relation
Status = IntelAffiliation.Status
Source = IntelAffiliation.Source
GROUP_KINDS = (Kind.ALLIANCE, Kind.CORPORATION)


@dataclass
class Partner:
    kind: str
    eve_id: int
    shared: int = 0
    militia_shared: int = 0
    against: int = 0
    months: set = field(default_factory=set)

    @property
    def first_month(self) -> date | None:
        return min(self.months) if self.months else None

    @property
    def last_month(self) -> date | None:
        return max(self.months) if self.months else None


def window(today: date | None = None) -> list[date]:
    return month_starts(today or timezone.now().date(), WINDOW_MONTHS)


def sampled_kills(entity_id: int, months: list[date]) -> int:
    return (
        IntelSampleMonth.objects.filter(
            entity_id=entity_id, month__in=months
        ).aggregate(total=Sum("kills"))["total"]
        or 0
    )


def partners(entity: IntelEntity, months: list[date]) -> dict:
    """``(kind, eve_id) -> Partner`` for the group's evidence window."""
    found: dict[tuple[str, int], Partner] = {}
    rows = IntelCoAttack.objects.filter(
        entity=entity, month__in=months, partner_kind__in=GROUP_KINDS
    ).values_list(
        "partner_kind",
        "partner_id",
        "month",
        "shared",
        "militia_shared",
        "against",
    )
    for kind, eve_id, month, shared, militia, against in rows:
        partner = found.setdefault((kind, eve_id), Partner(kind, eve_id))
        partner.shared += shared
        partner.militia_shared += militia
        partner.against += against
        if shared:
            partner.months.add(month)
    return found


def _active_months(entity: IntelEntity, months: list[date]) -> int:
    return IntelSampleMonth.objects.filter(
        entity=entity, month__in=months, kills__gt=0
    ).count()


def _reverse(partner_entity: IntelEntity, subject: IntelEntity, months):
    """What the partner's own investigation saw of the subject."""
    totals = IntelCoAttack.objects.filter(
        entity=partner_entity,
        month__in=months,
        partner_kind=subject.kind,
        partner_id=subject.eve_id,
    ).aggregate(shared=Sum("shared"), against=Sum("against"))
    return totals["shared"] or 0, totals["against"] or 0


def _was_member(subject: IntelEntity, partner: Partner) -> str | None:
    """The date a corporation joined the partner alliance, if it ever did."""
    if subject.kind != Kind.CORPORATION or partner.kind != Kind.ALLIANCE:
        return None
    for row in subject.alliance_history or []:
        if row.get("alliance_id") == partner.eve_id:
            return row.get("start_date") or "?"
    return None


@dataclass
class Verdict:
    partner: IntelEntity
    relation: str
    confidence: float
    evidence: dict
    first_month: date | None
    last_month: date | None


def _queue(kind: str, eve_id: int, priority: int) -> IntelEntity:
    entity, _ = IntelEntity.objects.get_or_create(kind=kind, eve_id=eve_id)
    if entity.status in (IntelEntity.Status.NEW, IntelEntity.Status.FAILED):
        entity.status = IntelEntity.Status.QUEUED
        entity.queued_at = timezone.now()
        entity.priority = max(entity.priority, priority)
        entity.save(
            update_fields=["status", "queued_at", "priority", "updated_at"]
        )
    return entity


def queue_partners(entity: IntelEntity, months: list[date] | None = None):
    """Queue the groups a finished investigation flew with most."""
    months = months or window()
    found = partners(entity, months)
    top = sorted(
        (p for p in found.values() if len(p.months) >= 2),
        key=lambda p: -p.shared,
    )[:QUEUE_TOP_PARTNERS]
    for partner in top:
        _queue(partner.kind, partner.eve_id, PARTNER_PRIORITY)
    return len(top)


def judge(entity: IntelEntity, months: list[date]) -> Verdict | None:
    """The one group this group leans on, over the whole window or the
    last year, whichever says so more strongly (a group that attached
    itself last spring shouldn't be diluted by the year before)."""
    verdicts = [
        _judge_window(entity, span)
        for span in (months, months[:RECENT_MONTHS])
        if span
    ]
    verdicts = [v for v in verdicts if v is not None]
    if not verdicts:
        return None
    return max(verdicts, key=lambda v: v.evidence["share"])


def _judge_window(entity: IntelEntity, months: list[date]) -> Verdict | None:
    kills = sampled_kills(entity.pk, months)
    if kills < MIN_KILLS:
        return None
    candidates = []
    for partner in partners(entity, months).values():
        share = partner.shared / kills
        if share < PET_SHARE or len(partner.months) < MIN_MONTHS_TOGETHER:
            continue
        if partner.militia_shared / partner.shared >= MILITIA_SHARE:
            continue
        candidates.append((share, partner))
    for share, partner in sorted(candidates, key=lambda c: -c[0]):
        other = IntelEntity.objects.filter(
            kind=partner.kind, eve_id=partner.eve_id
        ).first()
        if other is None or other.status != IntelEntity.Status.DONE:
            # Judged once the partner's own history is in.
            _queue(partner.kind, partner.eve_id, PARTNER_PRIORITY)
            continue
        other_kills = sampled_kills(other.pk, months)
        if other_kills < MIN_KILLS:
            continue
        reverse_shared, reverse_against = _reverse(other, entity, months)
        against = partner.against + reverse_against
        if against > max(
            MAX_AGAINST_FLOOR, MAX_AGAINST_SHARE * partner.shared
        ):
            continue
        reverse_share = reverse_shared / other_kills
        if share >= PET_ASYMMETRY * reverse_share:
            relation = Relation.PET
        elif kills <= other_kills:
            relation = Relation.ALLY
        else:
            # The partner is the smaller one; it is judged from its side.
            continue
        member_since = _was_member(entity, partner)
        active = _active_months(entity, months)
        # How much it leans, in how many of its active months, and how
        # rarely the two shoot each other.
        confidence = (
            min(1.0, share / 0.3)
            * min(1.0, len(partner.months) / max(MIN_MONTHS_TOGETHER, active))
            * (1 - against / partner.shared)
        )
        if member_since:
            confidence = min(1.0, confidence + 0.25)
        evidence = {
            "partner": {"kind": other.kind, "id": other.eve_id},
            "partner_name": other.name,
            "kills_sampled": kills,
            "shared": partner.shared,
            "share": round(share, 3),
            "reverse_share": round(reverse_share, 3),
            "months_together": len(partner.months),
            "months_active": active,
            "months_sampled": len(months),
            "against": against,
            "militia_shared": partner.militia_shared,
        }
        if member_since:
            evidence["member_since"] = member_since
        return Verdict(
            partner=other,
            relation=relation,
            confidence=round(confidence, 2),
            evidence=evidence,
            first_month=partner.first_month,
            last_month=partner.last_month,
        )
    return None


def bloc_of(entity: IntelEntity, *, create: bool = True) -> IntelBloc | None:
    """The bloc a group belongs to, making it the anchor of a new one."""
    anchored = IntelBloc.objects.filter(anchor=entity).first()
    if anchored:
        return anchored
    row = (
        IntelAffiliation.objects.filter(
            entity=entity,
            status__in=[Status.CONFIRMED, Status.SUGGESTED],
            ended=False,
        )
        .select_related("bloc")
        .order_by("status", "-confidence")  # "confirmed" < "suggested"
        .first()
    )
    if row:
        return row.bloc
    if not create:
        return None
    return IntelBloc.objects.create(
        name=entity.name or f"{entity.get_kind_display()} {entity.eve_id}",
        anchor=entity,
    )


def _save(
    entity: IntelEntity,
    bloc: IntelBloc,
    *,
    relation: str,
    confidence: float,
    evidence: dict,
    first_month,
    last_month,
) -> IntelAffiliation | None:
    row = IntelAffiliation.objects.filter(entity=entity, bloc=bloc).first()
    if row is None:
        return IntelAffiliation.objects.create(
            entity=entity,
            bloc=bloc,
            relation=relation,
            confidence=confidence,
            evidence=evidence,
            first_month=first_month,
            last_month=last_month,
        )
    if row.status == Status.REJECTED:
        return None
    row.evidence = evidence
    row.confidence = confidence
    row.first_month = min(filter(None, [row.first_month, first_month]))
    row.last_month = max(filter(None, [row.last_month, last_month]))
    row.ended = False
    if row.status == Status.SUGGESTED and row.source == Source.INFERRED:
        row.relation = relation
    row.save()
    return row


def score_group(entity: IntelEntity, months: list[date] | None = None):
    """Suggest (or refresh) the one bloc this group leans on."""
    months = months or window()
    verdict = judge(entity, months)
    if verdict is None:
        return None
    bloc = bloc_of(verdict.partner)
    if bloc is None or bloc.anchor_id == entity.pk:
        return None
    with transaction.atomic():
        row = _save(
            entity,
            bloc,
            relation=verdict.relation,
            confidence=verdict.confidence,
            evidence=verdict.evidence,
            first_month=verdict.first_month,
            last_month=verdict.last_month,
        )
        if row is not None:
            # Its parent changed: drop the stale suggestion to the old one.
            IntelAffiliation.objects.filter(
                entity=entity,
                status=Status.SUGGESTED,
                source=Source.INFERRED,
            ).exclude(pk=row.pk).delete()
    return row


def _member_groups(bloc: IntelBloc) -> list[int]:
    """Entity ids of the bloc's groups: the anchor and live affiliations."""
    ids = list(
        IntelAffiliation.objects.filter(
            bloc=bloc,
            entity__kind__in=GROUP_KINDS,
            status__in=[Status.CONFIRMED, Status.SUGGESTED],
            ended=False,
        ).values_list("entity_id", flat=True)
    )
    if bloc.anchor_id:
        ids.append(bloc.anchor_id)
    return ids


def our_character_ids() -> set[int]:
    return set(EveCharacter.objects.values_list("character_id", flat=True))


def score_associates(bloc: IntelBloc, months: list[date], ours: set[int]):
    """Suggest the characters outside the bloc who keep flying with it."""
    member_ids = _member_groups(bloc)
    member_eve_ids = set(
        IntelEntity.objects.filter(pk__in=member_ids).values_list(
            "eve_id", flat=True
        )
    )
    rows = (
        IntelCoAttack.objects.filter(
            entity_id__in=member_ids,
            month__in=months,
            partner_kind=Kind.CHARACTER,
        )
        .values("partner_id")
        .annotate(
            shared=Sum("shared"),
            months=Count("month", distinct=True),
            first=Min("month"),
            last=Max("month"),
            group=Max("partner_group"),
        )
        .filter(shared__gte=ASSOCIATE_SHARED, months__gte=ASSOCIATE_MONTHS)
    )
    found = [
        row
        for row in rows
        if row["group"] not in member_eve_ids
        and row["group"] != MINMATAR_FLEET_ALLIANCE_ID
        and row["partner_id"] not in ours
    ]
    if not found:
        return 0
    names = names_for(row["partner_id"] for row in found)
    saved = 0
    for row in found:
        entity, _ = IntelEntity.objects.get_or_create(
            kind=Kind.CHARACTER, eve_id=row["partner_id"]
        )
        if names.get(entity.eve_id) and entity.name != names[entity.eve_id]:
            entity.name = names[entity.eve_id]
            entity.save(update_fields=["name", "updated_at"])
        confidence = min(1.0, row["shared"] / 20) * min(1.0, row["months"] / 6)
        saved += bool(
            _save(
                entity,
                bloc,
                relation=Relation.ASSOCIATE,
                confidence=round(confidence, 2),
                evidence={
                    "shared": row["shared"],
                    "months_together": row["months"],
                    "flies_for": row["group"],
                },
                first_month=row["first"],
                last_month=row["last"],
            )
        )
    return saved


def end_stale(months: list[date]) -> int:
    """Inferred affiliations with no evidence for six months have ended."""
    cutoff = months[min(ENDED_AFTER_MONTHS, len(months)) - 1]
    return IntelAffiliation.objects.filter(
        source=Source.INFERRED, ended=False, last_month__lt=cutoff
    ).update(ended=True, updated_at=timezone.now())


def score_all(today: date | None = None) -> dict:
    """Rescore every investigated group, then associates, then endings."""
    months = window(today)
    stats = defaultdict(int)
    for entity in IntelEntity.objects.filter(
        kind__in=GROUP_KINDS, status=IntelEntity.Status.DONE
    ):
        stats["groups"] += 1
        stats["affiliations"] += bool(score_group(entity, months))
    ours = our_character_ids()
    for bloc in IntelBloc.objects.all():
        stats["associates"] += score_associates(bloc, months, ours)
    stats["ended"] = end_stale(months)
    # Blocs scoring named after their anchor follow its name.
    for bloc in IntelBloc.objects.filter(
        manual=False, anchor__isnull=False
    ).select_related("anchor"):
        if bloc.anchor.name and bloc.name != bloc.anchor.name:
            bloc.name = bloc.anchor.name
            bloc.save(update_fields=["name", "updated_at"])
    # Blocs scoring made that never got an affiliation. One with only
    # rejected rows stays, so the rejection is remembered.
    stats["empty_blocs"] = IntelBloc.objects.filter(
        manual=False, affiliations__isnull=True
    ).delete()[0]
    resolve.invalidate()
    return dict(stats)
