"""Who may edit/review doctrines and fittings on the site, and the diffs."""

import difflib

from fittings.eft import parse_eft_header
from fittings.helpers.permissions import (
    can_approve_doctrine_request,
    can_approve_fitting_request,
)
from fittings.models import (
    DOCTRINE_FITTING_ROLE_LABELS,
    DOCTRINE_FITTING_ROLES,
    EVE_FITTING_VERSIONED_FIELDS,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveFitting,
    EveFittingChangeRequest,
    composition_snapshot_for_doctrine,
)
from groups.helpers.feature_access import can_use_feature

TIER_PERMISSIONS = (
    "fittings.change_doctrine_non_strategic",
    "fittings.change_doctrine_strategic",
    "fittings.change_doctrine_fitting_non_strategic",
    "fittings.change_doctrine_fitting_strategic",
    "fittings.approve_doctrine_non_strategic",
    "fittings.approve_doctrine_strategic",
    "fittings.approve_doctrine_fitting_non_strategic",
    "fittings.approve_doctrine_fitting_strategic",
)

REQUEST_MODELS = {
    "fitting": EveFittingChangeRequest,
    "doctrine": EveDoctrineChangeRequest,
}


def can_edit_doctrines(user) -> bool:
    """May open the editor and the review queue (propose or approve)."""
    if user is None or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if can_use_feature(user, "fittings.doctrine.propose"):
        return True
    if can_use_feature(user, "fittings.doctrine.approve"):
        return True
    return any(user.has_perm(perm) for perm in TIER_PERMISSIONS)


def can_review_request(user, kind: str, tier: str) -> bool:
    if kind == "doctrine":
        return can_approve_doctrine_request(user, tier)
    return can_approve_fitting_request(user, tier)


def text_diff(current: str, proposed: str) -> list[dict]:
    """Line diff as [{kind: add|del|same, text}]."""
    cur = current.splitlines()
    new = proposed.splitlines()
    lines = []
    matcher = difflib.SequenceMatcher(a=cur, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            lines.extend({"kind": "same", "text": t} for t in cur[i1:i2])
            continue
        lines.extend({"kind": "del", "text": t} for t in cur[i1:i2])
        lines.extend({"kind": "add", "text": t} for t in new[j1:j2])
    return lines


def _field_diff(field: str, label: str, current: str, proposed: str):
    if current == proposed:
        return None
    return {
        "field": field,
        "label": label,
        "lines": text_diff(current, proposed),
    }


def _as_text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def fitting_diffs(fitting: EveFitting, payload: dict) -> list[dict]:
    diffs = []
    for field in EVE_FITTING_VERSIONED_FIELDS:
        current = (
            fitting.tag_slugs() if field == "tags" else getattr(fitting, field)
        )
        proposed = payload.get(field, current)
        if field == "tags":
            current = sorted(current or [])
            proposed = sorted(proposed or [])
        row = _field_diff(
            field,
            "EFT" if field == "eft_format" else field.replace("_", " "),
            _as_text(current),
            _as_text(proposed),
        )
        if row:
            diffs.append(row)
    return diffs


def doctrine_diffs(doctrine: EveDoctrine, payload: dict) -> list[dict]:
    diffs = []
    for field in ("name", "type", "description"):
        row = _field_diff(
            field,
            field,
            _as_text(getattr(doctrine, field)),
            _as_text(payload.get(field)),
        )
        if row:
            diffs.append(row)
    current = composition_snapshot_for_doctrine(doctrine)
    proposed = payload.get("composition") or {}
    ids = set()
    for role in DOCTRINE_FITTING_ROLES:
        ids |= set(current.get(role) or []) | set(proposed.get(role) or [])
    names = dict(
        EveFitting.all_objects.filter(pk__in=ids).values_list("pk", "name")
    )
    for role in DOCTRINE_FITTING_ROLES:
        row = _field_diff(
            f"composition.{role}",
            DOCTRINE_FITTING_ROLE_LABELS[role],
            _as_text(
                sorted(names.get(i, str(i)) for i in current.get(role) or [])
            ),
            _as_text(
                sorted(names.get(i, str(i)) for i in proposed.get(role) or [])
            ),
        )
        if row:
            diffs.append(row)
    return diffs


def _name(user) -> str | None:
    return user.username if user else None


def serialize_request(user, kind: str, change_request) -> dict:
    if kind == "doctrine":
        target = change_request.doctrine
        diffs = doctrine_diffs(target, change_request.payload)
    else:
        target = EveFitting.all_objects.get(pk=change_request.fitting_id)
        diffs = fitting_diffs(target, change_request.payload)
    pending = change_request.status == "pending"
    reviewer = can_review_request(user, kind, change_request.tier)
    return {
        "kind": kind,
        "id": change_request.pk,
        "target_id": target.pk,
        "target_name": target.name,
        "target_ship_id": target.ship_id if kind == "fitting" else None,
        "status": change_request.status,
        "tier": change_request.tier,
        "change_kind": change_request.change_kind,
        "submitted_by": _name(change_request.submitted_by),
        "submitted_at": change_request.submitted_at.isoformat(),
        "reviewed_by": _name(change_request.reviewed_by),
        "reviewed_at": (
            change_request.reviewed_at.isoformat()
            if change_request.reviewed_at
            else None
        ),
        "review_note": change_request.review_note,
        "submit_note": getattr(change_request, "submit_note", ""),
        "can_review": pending and reviewer,
        "can_cancel": pending
        and (change_request.submitted_by_id == user.id or reviewer),
        "diffs": diffs,
    }


def eft_ship_matches(fitting: EveFitting, eft: str) -> bool:
    """The edited EFT must stay on the fit's current hull."""
    return parse_eft_header(eft)[0] == parse_eft_header(fitting.eft_format)[0]
