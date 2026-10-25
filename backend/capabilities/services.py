"""
Database side of the capability engine: load inputs, run the pure engine,
store results. Called from capabilities.tasks only; never from a request.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import requests
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from capabilities.engine import rules
from capabilities.engine import sde as sde_mod
from capabilities.engine.fit import parse_fit
from capabilities.engine.readiness import FitChecker, evaluate
from capabilities.engine.requirements import (
    Override,
    Requirements,
    Row,
    compute,
)
from capabilities.models import (
    CharacterAccount,
    CharacterAccountLink,
    CharacterAccountMember,
    CharacterCapability,
    CharacterFittingReadiness,
    FittingRequirementSet,
    FittingSkillRequirement,
    SdeSnapshot,
)
from eveonline.models import EveCharacter, EveCharacterSkill
from fittings.models import (
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrineFitting,
    EveFitting,
)
from fleets.models import (
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)

logger = logging.getLogger(__name__)

KEEP_SNAPSHOTS = 3
HTTP_TIMEOUT = 60
# Characters stay in fleet for a few minutes after logging off, so a short
# overlap can be an account swap. Longer than this means two accounts.
ACCOUNT_OVERLAP = timedelta(minutes=10)
CHARACTERS_PER_ACCOUNT = 3
ROLE_ORDER = {"primary": 0, "secondary": 1, "support": 2, "utility": 3}

# Hulls outside every doctrine map to a capability by group.
GROUP_CAPABILITY = {
    "Logistics": "Logistics",
    "Logistics Frigate": "Logistics",
    "Force Auxiliary": "Logistics",
    "Command Ship": "Links",
    "Command Destroyer": "Links",
    "Interdictor": "Tackle",
    "Heavy Interdiction Cruiser": "Tackle",
    "Interceptor": "Tackle",
    "Combat Recon Ship": "Support",
    "Electronic Attack Ship": "Support",
    "Force Recon Ship": "Recon",
    "Black Ops": "Recon",
    "Covert Ops": "Recon",
    "Dreadnought": "Dreads",
    "Lancer Dreadnought": "Dreads",
    "Carrier": "Carriers",
    "Supercarrier": "Carriers",
}
NON_COMBAT_GROUP_WORDS = (
    "capsule",
    "shuttle",
    "industrial",
    "freighter",
    "hauler",
    "mining",
    "exhumer",
    "barge",
    "transport",
    "corvette",
    "rookie",
    "titan",
)


def _upsert(model, rows, unique_fields, update_fields):
    """bulk_create that updates on conflict. MySQL upserts on any unique
    key and refuses unique_fields; SQLite and Postgres need them."""
    target = {}
    if connection.features.supports_update_conflicts_with_target:
        target["unique_fields"] = unique_fields
    model.objects.bulk_create(
        rows,
        batch_size=1000,
        update_conflicts=True,
        update_fields=update_fields,
        **target,
    )


# ---------------------------------------------------------------- SDE
_SDE_CACHE: dict[int, sde_mod.SdeData] = {}


def current_snapshot() -> SdeSnapshot | None:
    return (
        SdeSnapshot.objects.filter(is_current=True).order_by("-build").first()
    )


def current_sde() -> sde_mod.SdeData | None:
    snap = (
        SdeSnapshot.objects.filter(is_current=True)
        .order_by("-build")
        .values_list("build", flat=True)
        .first()
    )
    if snap is None:
        return None
    if snap not in _SDE_CACHE:
        blob = SdeSnapshot.objects.values_list("data", flat=True).get(
            build=snap
        )
        _SDE_CACHE.clear()
        _SDE_CACHE[snap] = sde_mod.SdeData(sde_mod.unpack(bytes(blob)))
    return _SDE_CACHE[snap]


def latest_published_build() -> int:
    response = requests.get(sde_mod.LATEST_URL, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    first = response.text.strip().splitlines()[0]
    return int(json.loads(first)["buildNumber"])


def download_build(build: int, directory: str) -> Path:
    path = Path(directory) / f"sde-{build}.zip"
    with requests.get(
        sde_mod.ZIP_URL.format(build=build), stream=True, timeout=HTTP_TIMEOUT
    ) as response:
        response.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    return path


def store_snapshot(snapshot: dict) -> SdeSnapshot:
    """Save a built snapshot as current and prune old builds."""
    blob = sde_mod.pack(snapshot)
    with transaction.atomic():
        row, _ = SdeSnapshot.objects.update_or_create(
            build=snapshot["build"],
            defaults={
                "release_date": snapshot.get("release_date", ""),
                "data": blob,
                "size": len(blob),
                "is_current": True,
            },
        )
        SdeSnapshot.objects.exclude(pk=row.pk).update(is_current=False)
        keep = SdeSnapshot.objects.order_by("-build").values_list(
            "pk", flat=True
        )[:KEEP_SNAPSHOTS]
        SdeSnapshot.objects.exclude(pk__in=list(keep)).delete()
    _SDE_CACHE.clear()
    return row


def load_snapshot_from_path(path: str | Path) -> SdeSnapshot:
    return store_snapshot(sde_mod.build_snapshot(path))


def update_sde_if_new() -> int | None:
    """Download and store CCP's newest build when it is newer. Returns it."""
    latest = latest_published_build()
    current = current_snapshot()
    if current and current.build >= latest:
        return None
    with tempfile.TemporaryDirectory() as directory:
        path = download_build(latest, directory)
        snapshot = sde_mod.build_snapshot(path)
    store_snapshot(snapshot)
    logger.info("Loaded SDE build %s", latest)
    return latest


# ---------------------------------------------------------------- inputs
def doctrine_fittings() -> dict[int, dict]:
    """{fitting id: {"fitting", "roles", "strategic"}} for doctrine fittings."""
    out: dict[int, dict] = {}
    rows = EveDoctrineFitting.objects.filter(
        fitting__deleted__isnull=True
    ).select_related("fitting", "doctrine")
    for df in rows:
        entry = out.setdefault(
            df.fitting_id,
            {"fitting": df.fitting, "roles": [], "strategic": False},
        )
        entry["roles"].append(df.role)
        if df.doctrine.type == DOCTRINE_TYPE_STRATEGIC:
            entry["strategic"] = True
    return out


def scope_characters():
    """Characters the engine rates: every character that belongs to a user."""
    return EveCharacter.objects.filter(user__isnull=False)


def skill_maps(character_pks) -> dict[int, dict[int, int]]:
    """{EveCharacter pk: {skill id: trained level}}."""
    out: dict[int, dict[int, int]] = defaultdict(dict)
    rows = EveCharacterSkill.objects.filter(
        character_id__in=list(character_pks)
    )
    for pk, skill, level in rows.values_list(
        "character_id", "skill_id", "skill_level"
    ):
        if level > out[pk].get(skill, 0):
            out[pk][skill] = level
    return out


def seat_rows(since, character_ids=None):
    """(character EVE id, fleet instance id, hull, start time, fleet type)."""
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__start_time__gte=since
    )
    snapshots = EveFleetInstanceMemberShipSnapshot.objects.filter(
        member__eve_fleet_instance__start_time__gte=since
    )
    if character_ids is not None:
        members = members.filter(character_id__in=list(character_ids))
        snapshots = snapshots.filter(
            member__character_id__in=list(character_ids)
        )
    members = members.values_list(
        "character_id",
        "eve_fleet_instance_id",
        "ship_type_id",
        "eve_fleet_instance__start_time",
        "eve_fleet_instance__eve_fleet__type",
    )
    snapshots = snapshots.values_list(
        "member__character_id",
        "member__eve_fleet_instance_id",
        "ship_type_id",
        "member__eve_fleet_instance__start_time",
        "member__eve_fleet_instance__eve_fleet__type",
    )
    seen = set()
    for row in list(members) + list(snapshots):
        key = row[:3]
        if key not in seen:
            seen.add(key)
            yield row


def proven_window_start():
    return timezone.now() - timedelta(days=rules.PROVEN_WINDOW_DAYS)


def proven_by_hull(hulls) -> dict[int, list[int]]:
    """{hull: [EveCharacter pk]} with PROVEN_MIN_FLEETS+ fleets in it."""
    hulls = set(hulls)
    fleets: dict[tuple[int, int], set] = defaultdict(set)
    for character_id, instance, hull, _, _ in seat_rows(proven_window_start()):
        if hull in hulls:
            fleets[(character_id, hull)].add(instance)
    pk_by_eve_id = dict(scope_characters().values_list("character_id", "pk"))
    out: dict[int, list[int]] = defaultdict(list)
    for (character_id, hull), instances in fleets.items():
        pk = pk_by_eve_id.get(character_id)
        if pk and len(instances) >= rules.PROVEN_MIN_FLEETS:
            out[hull].append(pk)
    return out


# ---------------------------------------------------------------- requirements
def _overrides(fitting: EveFitting) -> list[Override]:
    return [
        Override(
            skill=o.skill_id,
            action=o.action,
            tier=o.tier,
            level=o.level,
            note=o.note,
        )
        for o in fitting.skill_overrides.all()
    ]


def _substitutes(fitting: EveFitting) -> dict[int, list[int]]:
    out: dict[int, list[int]] = defaultdict(list)
    for pref, sub in fitting.module_substitutions.values_list(
        "preferred_module_id", "substitute_module_id"
    ):
        out[pref].append(sub)
    return dict(out)


def _input_key(
    fitting, entry, sde, overrides, substitutes, proven_count
) -> str:
    payload = json.dumps(
        [
            fitting.latest_version,
            fitting.eft_format,
            fitting.minimum_pod,
            fitting.capability,
            sorted(entry["roles"]),
            entry["strategic"],
            sde.build,
            rules.RULES_VERSION,
            [o.__dict__ for o in overrides],
            sorted((k, sorted(v)) for k, v in substitutes.items()),
            proven_count,
        ],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:64]


def current_set(fitting_id: int) -> FittingRequirementSet | None:
    return (
        FittingRequirementSet.objects.filter(
            fitting_id=fitting_id, is_current=True
        )
        .order_by("-pk")
        .first()
    )


def recompute_fitting(
    fitting_id: int,
    *,
    entry: dict | None = None,
    proven: dict[int, list[int]] | None = None,
    skills: dict[int, dict[int, int]] | None = None,
    force: bool = False,
) -> FittingRequirementSet | None:
    """Compute and store one fitting's requirements. None when not a doctrine fit."""
    sde = current_sde()
    if sde is None:
        logger.debug("No SDE snapshot loaded; run load_sde_snapshot")
        return None
    if entry is None:
        entry = doctrine_fittings().get(fitting_id)
    if entry is None:
        FittingRequirementSet.objects.filter(
            fitting_id=fitting_id, is_current=True
        ).update(is_current=False)
        CharacterFittingReadiness.objects.filter(
            fitting_id=fitting_id
        ).delete()
        return None
    fitting = entry["fitting"]
    fit = parse_fit(sde, fitting.eft_format, fitting.minimum_pod)
    if fit.hull is None:
        logger.warning("Fitting %s: unknown hull", fitting.pk)
        return None
    if proven is None:
        proven = proven_by_hull([fit.hull])
    pilots = proven.get(fit.hull, [])
    if skills is None:
        skills = skill_maps(pilots)
    overrides = _overrides(fitting)
    substitutes = _substitutes(fitting)
    key = _input_key(fitting, entry, sde, overrides, substitutes, len(pilots))
    existing = current_set(fitting_id)
    if existing and existing.input_key == key and not force:
        return existing
    req = compute(
        sde,
        fit,
        roles=entry["roles"],
        capability_override=fitting.capability or None,
        proven_skills=[skills.get(pk, {}) for pk in pilots],
        substitutes=substitutes,
        overrides=overrides,
    )
    with transaction.atomic():
        FittingRequirementSet.objects.filter(fitting_id=fitting_id).update(
            is_current=False
        )
        rs = FittingRequirementSet.objects.create(
            fitting=fitting,
            fitting_version=fitting.latest_version or "",
            sde_build=sde.build,
            rules_version=rules.RULES_VERSION,
            input_key=key,
            capability=req.capability,
            capability_source="override" if fitting.capability else "auto",
            strategic=entry["strategic"],
            tank_layers=req.tank_layers,
            alternatives={str(k): v for k, v in req.alternatives.items()},
            alternative_requirements={
                str(k): {str(s): lv for s, lv in v.items()}
                for k, v in req.alternative_requirements.items()
            },
            unknown_items=req.unknown_items,
            proven_pilots=req.proven_pilots,
            proven_pass_rate=req.proven_pass_rate,
        )
        FittingSkillRequirement.objects.bulk_create(
            [_row_model(rs, r) for r in req.rows.values()]
        )
        # Keep the last few sets for comparison; drop older ones.
        old = (
            FittingRequirementSet.objects.filter(fitting_id=fitting_id)
            .order_by("-pk")
            .values_list("pk", flat=True)[5:]
        )
        FittingRequirementSet.objects.filter(pk__in=list(old)).delete()
    return rs


def _row_model(rs, r: Row) -> FittingSkillRequirement:
    return FittingSkillRequirement(
        requirement_set=rs,
        skill_id=r.skill,
        skill_name=r.name,
        required_level=r.required_level,
        fit_level=r.fit_level,
        core_level=r.core_level,
        optimal_level=r.optimal_level,
        sources=r.sources,
        bucket=r.bucket,
        per_level_bonus=r.per_level,
        weight=r.weight,
        reason=r.reason[:255],
        mastery_levels=r.mastery,
        empirical_level=r.empirical_level,
        proven_meeting_core=r.proven_meeting_core,
        overridden=r.overridden,
    )


def requirements_from_set(rs: FittingRequirementSet) -> Requirements:
    """Rebuild the engine result from stored rows (for readiness)."""
    rows = {}
    for m in rs.rows.all():
        rows[m.skill_id] = Row(
            skill=m.skill_id,
            name=m.skill_name,
            required_level=m.required_level,
            fit_level=m.fit_level,
            core_level=m.core_level,
            optimal_level=m.optimal_level,
            sources=m.sources,
            bucket=m.bucket,
            per_level=m.per_level_bonus,
            reason=m.reason,
        )
    return Requirements(
        capability=rs.capability,
        tank_layers=rs.tank_layers,
        rows=rows,
        alternatives={int(k): v for k, v in rs.alternatives.items()},
        alternative_requirements={
            int(k): {int(s): lv for s, lv in v.items()}
            for k, v in rs.alternative_requirements.items()
        },
    )


def recompute_all_requirements(force: bool = False) -> list[int]:
    """Every doctrine fitting. Returns the fitting ids whose set changed."""
    sde = current_sde()
    if sde is None:
        return []
    entries = doctrine_fittings()
    hulls = {}
    for fid, entry in entries.items():
        fit = parse_fit(sde, entry["fitting"].eft_format)
        if fit.hull:
            hulls[fid] = fit.hull
    proven = proven_by_hull(hulls.values())
    skills = skill_maps({pk for pks in proven.values() for pk in pks})
    changed = []
    for fid, entry in entries.items():
        before = current_set(fid)
        rs = recompute_fitting(
            fid, entry=entry, proven=proven, skills=skills, force=force
        )
        if rs and (before is None or before.pk != rs.pk):
            changed.append(fid)
    # Fittings that left every doctrine.
    stale = FittingRequirementSet.objects.filter(is_current=True).exclude(
        fitting_id__in=list(entries)
    )
    for fid in set(stale.values_list("fitting_id", flat=True)):
        recompute_fitting(fid, entry=None)
    return changed


def needs_full_recompute() -> bool:
    sde = current_sde()
    if sde is None:
        return False
    return (
        FittingRequirementSet.objects.filter(is_current=True)
        .filter(
            ~Q(sde_build=sde.build) | ~Q(rules_version=rules.RULES_VERSION)
        )
        .exists()
    )


# ---------------------------------------------------------------- readiness
class _FittingContext:
    def __init__(self, sde, rs: FittingRequirementSet):
        fitting = rs.fitting
        self.rs = rs
        self.fit = parse_fit(sde, fitting.eft_format, fitting.minimum_pod)
        self.req = requirements_from_set(rs)
        self.checker = FitChecker(sde, self.fit, self.req)
        self.hull_req = sde.with_prerequisites(
            sde.required_skills(self.fit.hull)
        )


# Per worker process: a requirement set never changes once stored, so its
# parsed fit and memoized fit checks stay valid until a new set replaces it.
_CONTEXT_CACHE: dict[tuple, _FittingContext] = {}


def _contexts(sde, fitting_ids=None) -> list[_FittingContext]:
    sets = FittingRequirementSet.objects.filter(is_current=True)
    if fitting_ids is not None:
        sets = sets.filter(fitting_id__in=list(fitting_ids))
    keys = {
        pk: (sde.build, pk, input_key)
        for pk, input_key in sets.values_list("pk", "input_key")
    }
    missing = [pk for pk, key in keys.items() if key not in _CONTEXT_CACHE]
    if missing:
        for rs in (
            FittingRequirementSet.objects.filter(pk__in=missing)
            .select_related("fitting")
            .prefetch_related("rows")
        ):
            _CONTEXT_CACHE[keys[rs.pk]] = _FittingContext(sde, rs)
    if fitting_ids is None:
        for key in set(_CONTEXT_CACHE) - set(keys.values()):
            del _CONTEXT_CACHE[key]
    return [_CONTEXT_CACHE[key] for key in keys.values()]


def refresh_readiness(fitting_ids=None, character_pks=None) -> int:
    """Rewrite CharacterFittingReadiness for these fittings × characters."""
    sde = current_sde()
    if sde is None:
        return 0
    contexts = _contexts(sde, fitting_ids)
    if not contexts:
        return 0
    characters = scope_characters()
    if character_pks is not None:
        characters = characters.filter(pk__in=list(character_pks))
    pks = list(characters.values_list("pk", flat=True))
    written = 0
    for start in range(0, len(pks), 500):
        chunk = pks[start : start + 500]
        skills = skill_maps(chunk)
        rows = []
        for pk in chunk:
            char_skills = skills.get(pk, {})
            for ctx in contexts:
                r = evaluate(
                    sde, ctx.req, ctx.checker, ctx.hull_req, char_skills
                )
                rows.append(
                    CharacterFittingReadiness(
                        character_id=pk,
                        fitting_id=ctx.rs.fitting_id,
                        requirement_set=ctx.rs,
                        unlocked=r.unlocked,
                        hard_ready=r.hard_ready,
                        core_ready=r.core_ready,
                        doctrine_ready=(
                            r.core_ready if ctx.rs.strategic else r.hard_ready
                        ),
                        missing_required=r.missing_required,
                        missing_core=r.missing_core,
                        fit_problems=r.fit_problems,
                        days_to_hard=r.days_to_hard,
                        days_to_core=r.days_to_core,
                        support_score=r.support_score,
                        computed_at=timezone.now(),
                    )
                )
        _upsert(
            CharacterFittingReadiness,
            rows,
            ["character", "fitting"],
            [
                "requirement_set",
                "unlocked",
                "hard_ready",
                "core_ready",
                "doctrine_ready",
                "missing_required",
                "missing_core",
                "fit_problems",
                "days_to_hard",
                "days_to_core",
                "support_score",
                "computed_at",
            ],
        )
        written += len(rows)
    # Fittings no longer rated.
    CharacterFittingReadiness.objects.exclude(
        fitting_id__in=FittingRequirementSet.objects.filter(
            is_current=True
        ).values("fitting_id")
    ).delete()
    return written


# ---------------------------------------------------------------- capabilities
def _hull_capabilities(sde) -> dict[int, list[tuple[int, str, int]]]:
    """{hull: [(fitting id, capability, role order)]} from current sets."""
    out: dict[int, list] = defaultdict(list)
    roles = defaultdict(lambda: 9)
    for fid, role in EveDoctrineFitting.objects.values_list(
        "fitting_id", "role"
    ):
        roles[fid] = min(roles[fid], ROLE_ORDER.get(role, 9))
    sets = FittingRequirementSet.objects.filter(is_current=True).values_list(
        "fitting_id", "fitting__ship_id", "capability"
    )
    for fitting_id, hull, capability in sets:
        out[hull].append((fitting_id, capability, roles[fitting_id]))
    for hull in out:
        out[hull].sort(key=lambda x: x[2])
    return out


def _group_capability(sde, hull: int) -> str | None:
    group = sde.group_name(hull)
    if not group or sde.category(hull) != sde_mod.CAT_SHIP:
        return None
    if group in GROUP_CAPABILITY:
        return GROUP_CAPABILITY[group]
    if any(w in group.lower() for w in NON_COMBAT_GROUP_WORDS):
        return None
    return "DPS"


def _flown(sde, pk_by_eve_id, subset: bool) -> dict[tuple[int, str], dict]:
    """{(character pk, capability): fleets, strategic fleets, last flown}."""
    hull_caps = _hull_capabilities(sde)
    hard_ready = set(
        CharacterFittingReadiness.objects.filter(
            character_id__in=list(pk_by_eve_id.values()), hard_ready=True
        ).values_list("character_id", "fitting_id")
    )
    flown: dict[tuple[int, str], dict] = defaultdict(
        lambda: {"fleets": set(), "strategic": set(), "last": None}
    )
    seats = seat_rows(
        proven_window_start(), list(pk_by_eve_id) if subset else None
    )
    for character_id, instance, hull, started, fleet_type in seats:
        pk = pk_by_eve_id.get(character_id)
        if pk is None:
            continue
        options = hull_caps.get(hull)
        if options:
            # A hull in several doctrine fits counts as the one they can fly.
            ready = [o for o in options if (pk, o[0]) in hard_ready]
            capability = (ready or options)[0][1]
        else:
            capability = _group_capability(sde, hull)
        if capability is None:
            continue
        entry = flown[(pk, capability)]
        entry["fleets"].add(instance)
        if fleet_type == "strategic":
            entry["strategic"].add(instance)
        if entry["last"] is None or started > entry["last"]:
            entry["last"] = started
    return flown


def _readiness_by_capability(pks) -> dict[tuple[int, str], dict]:
    """{(character pk, capability): unlocked/ready counts and best fitting}."""
    by_cap = dict(
        FittingRequirementSet.objects.filter(is_current=True).values_list(
            "fitting_id", "capability"
        )
    )
    out = defaultdict(
        lambda: {"unlocked": 0, "ready": 0, "best": None, "rank": None}
    )
    rows = CharacterFittingReadiness.objects.filter(
        character_id__in=list(pks)
    ).values_list(
        "character_id",
        "fitting_id",
        "unlocked",
        "doctrine_ready",
        "support_score",
    )
    for pk, fid, unlocked, ready, score in rows:
        cap = by_cap.get(fid)
        if cap is None:
            continue
        entry = out[(pk, cap)]
        entry["unlocked"] += unlocked
        entry["ready"] += ready
        rank = (ready, unlocked, score)
        if entry["rank"] is None or rank > entry["rank"]:
            entry["best"], entry["rank"] = fid, rank
    return out


def _capability_row(pk, capability, ready, flown) -> CharacterCapability:
    fleets = len(flown["fleets"]) if flown else 0
    if fleets >= rules.PROVEN_MIN_FLEETS:
        level = CharacterCapability.LEVEL_PROVEN
    elif ready and ready["ready"]:
        level = CharacterCapability.LEVEL_DOCTRINE_READY
    elif ready and ready["unlocked"]:
        level = CharacterCapability.LEVEL_UNLOCKED
    else:
        level = CharacterCapability.LEVEL_NONE
    return CharacterCapability(
        character_id=pk,
        capability=capability,
        level=level,
        best_fitting_id=ready["best"] if ready else None,
        ready_fittings=ready["ready"] if ready else 0,
        unlocked_fittings=ready["unlocked"] if ready else 0,
        fleets_365d=fleets,
        strategic_fleets_365d=len(flown["strategic"]) if flown else 0,
        last_flown=flown["last"] if flown else None,
        computed_at=timezone.now(),
    )


def refresh_capabilities(character_pks=None) -> int:
    sde = current_sde()
    if sde is None:
        return 0
    characters = scope_characters()
    if character_pks is not None:
        characters = characters.filter(pk__in=list(character_pks))
    pk_by_eve_id = dict(characters.values_list("character_id", "pk"))
    flown = _flown(sde, pk_by_eve_id, subset=character_pks is not None)
    readiness = _readiness_by_capability(pk_by_eve_id.values())
    rows = [
        _capability_row(
            pk,
            capability,
            readiness.get((pk, capability)),
            flown.get((pk, capability)),
        )
        for pk in pk_by_eve_id.values()
        for capability in rules.CAPABILITIES
    ]
    _upsert(
        CharacterCapability,
        rows,
        ["character", "capability"],
        [
            "level",
            "best_fitting",
            "ready_fittings",
            "unlocked_fittings",
            "fleets_365d",
            "strategic_fleets_365d",
            "last_flown",
            "computed_at",
        ],
    )
    return len(rows)


# ---------------------------------------------------------------- accounts
def refresh_account_links() -> int:
    """Pairs of a player's characters seen in one fleet at the same time."""
    owners = dict(scope_characters().values_list("character_id", "user_id"))
    pks = dict(scope_characters().values_list("character_id", "pk"))
    by_instance: dict[int, list] = defaultdict(list)
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__start_time__gte=proven_window_start(),
        character_id__in=list(owners),
    ).values_list(
        "eve_fleet_instance_id", "character_id", "join_time", "updated_at"
    )
    for instance, character_id, joined, last_seen in members:
        if joined and last_seen:
            by_instance[instance].append((character_id, joined, last_seen))
    pairs: dict[tuple[int, int], dict] = {}
    for rows in by_instance.values():
        for i, (a, a_start, a_end) in enumerate(rows):
            for b, b_start, b_end in rows[i + 1 :]:
                if a == b or owners[a] != owners[b]:
                    continue
                overlap = min(a_end, b_end) - max(a_start, b_start)
                if overlap < ACCOUNT_OVERLAP:
                    continue
                key = tuple(sorted((pks[a], pks[b])))
                entry = pairs.setdefault(
                    key, {"user": owners[a], "fleets": 0, "last": None}
                )
                entry["fleets"] += 1
                seen = min(a_end, b_end)
                if entry["last"] is None or seen > entry["last"]:
                    entry["last"] = seen
    with transaction.atomic():
        CharacterAccountLink.objects.all().delete()
        CharacterAccountLink.objects.bulk_create(
            [
                CharacterAccountLink(
                    user_id=v["user"],
                    character_a_id=a,
                    character_b_id=b,
                    fleets_together=v["fleets"],
                    last_seen_together=v["last"],
                )
                for (a, b), v in pairs.items()
            ],
            batch_size=1000,
        )
    infer_accounts()
    return len(pairs)


def group_accounts(
    characters: list[int], links: dict[frozenset, int]
) -> list[list[int]]:
    """Assign characters to accounts: linked characters never share one.

    The most-linked characters come first, so the player's core characters
    (the largest group seen online together) each open their own account.
    A character joins the first account it has no link with and that has
    room; characters without links stay unassigned.
    """
    degree = defaultdict(int)
    for pair, count in links.items():
        for c in pair:
            degree[c] += count
    accounts: list[list[int]] = []
    for c in sorted(characters, key=lambda x: (-degree[x], x)):
        if not degree[c]:
            continue
        for account in accounts:
            if len(account) < CHARACTERS_PER_ACCOUNT and not any(
                frozenset((c, other)) in links for other in account
            ):
                account.append(c)
                break
        else:
            accounts.append([c])
    return accounts


def infer_accounts() -> int:
    """Rebuild inferred accounts; users who placed characters themselves keep theirs."""
    links: dict[int, dict[frozenset, int]] = defaultdict(dict)
    for user, a, b, n in CharacterAccountLink.objects.values_list(
        "user_id", "character_a_id", "character_b_id", "fleets_together"
    ):
        links[user][frozenset((a, b))] = n
    pilot_users = set(
        CharacterAccount.objects.filter(
            source=CharacterAccount.SOURCE_PILOT
        ).values_list("user_id", flat=True)
    )
    count = 0
    with transaction.atomic():
        CharacterAccount.objects.filter(
            source=CharacterAccount.SOURCE_INFERRED
        ).exclude(user_id__in=pilot_users).delete()
        for user, user_links in links.items():
            if user in pilot_users:
                continue
            characters = sorted({c for pair in user_links for c in pair})
            for number, members in enumerate(
                group_accounts(characters, user_links), start=1
            ):
                account = CharacterAccount.objects.create(
                    user_id=user, number=number
                )
                CharacterAccountMember.objects.bulk_create(
                    [
                        CharacterAccountMember(character_id=c, account=account)
                        for c in members
                    ]
                )
                count += 1
    return count
