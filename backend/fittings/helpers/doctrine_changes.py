"""Submit, apply, and publish doctrine change requests."""

import uuid

from django.db import transaction
from django.utils import timezone

from fittings.models import (
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveDoctrineHistory,
    DOCTRINE_FITTING_ROLES,
    composition_snapshot_for_doctrine,
    location_ids_for_doctrine,
)
from fittings.helpers.permissions import (
    can_propose_doctrine_change,
    doctrine_change_tier,
    tier_covers,
)


def build_doctrine_payload_from_form(cleaned_data) -> dict:
    return {
        "name": cleaned_data["name"],
        "type": cleaned_data["type"],
        "description": cleaned_data["description"],
        "retired": bool(cleaned_data.get("retired")),
        "composition": {
            role: sorted(
                f.pk for f in cleaned_data.get(f"{role}_fittings", [])
            )
            for role in DOCTRINE_FITTING_ROLES
        },
        "location_ids": sorted(
            loc.pk for loc in cleaned_data.get("locations", [])
        ),
    }


def _normalized_composition(comp: dict) -> dict:
    return {
        role: sorted(comp.get(role) or []) for role in DOCTRINE_FITTING_ROLES
    }


def _retired_changed(doctrine: EveDoctrine, payload: dict) -> bool:
    # Payloads from before retiring existed carry no key: keep the state.
    if "retired" not in payload:
        return False
    return bool(payload["retired"]) != doctrine.retired


def doctrine_state_changed(doctrine: EveDoctrine, payload: dict) -> bool:
    if (doctrine.name, doctrine.type, doctrine.description) != (
        payload["name"],
        payload["type"],
        payload["description"],
    ):
        return True
    if _retired_changed(doctrine, payload):
        return True
    if _normalized_composition(
        composition_snapshot_for_doctrine(doctrine)
    ) != _normalized_composition(payload.get("composition") or {}):
        return True
    if location_ids_for_doctrine(doctrine) != sorted(
        payload.get("location_ids") or []
    ):
        return True
    return False


def _stored_doctrine(doctrine: EveDoctrine) -> EveDoctrine | None:
    """
    The saved row. The admin hands over an instance that already carries
    the form's values, so history and tiers must read the database.
    """
    if not doctrine.pk:
        return None
    # Soft-deleted doctrines stay addressable so a removal can be undone.
    return EveDoctrine.all_objects.filter(pk=doctrine.pk).first()


def _write_doctrine_history_if_needed(doctrine: EveDoctrine, payload: dict):
    stored = _stored_doctrine(doctrine)
    if stored is None or not stored.latest_version:
        return
    if not doctrine_state_changed(stored, payload):
        return
    EveDoctrineHistory.objects.create(
        doctrine=stored,
        superseded_version_id=stored.latest_version,
        name=stored.name,
        type=stored.type,
        description=stored.description,
        composition=composition_snapshot_for_doctrine(stored),
        location_ids=location_ids_for_doctrine(stored),
    )
    doctrine.latest_version = str(uuid.uuid4())


def change_tier_for(doctrine: EveDoctrine, payload: dict) -> str | None:
    """Review tier for applying payload to doctrine (None = applies now)."""
    stored = _stored_doctrine(doctrine)
    return doctrine_change_tier(
        stored.type if stored else None, payload.get("type", "")
    )


def validate_payload_matches_request_tier(
    doctrine: EveDoctrine, payload: dict, tier: str
) -> None:
    """
    A request can only be approved at a tier that covers both the live type
    and the proposed one (SEC-2): a lower-tier approver never publishes a
    change to, or out of, a more protected category.
    """
    needed = change_tier_for(doctrine, payload)
    if not tier_covers(tier, needed):
        raise ValueError(
            f"Payload doctrine type '{payload.get('type')}' needs a "
            f"'{needed}' review, not '{tier}'."
        )


def _require_pending_change_request(change_request) -> None:
    if change_request.status != ChangeRequestStatus.PENDING:
        raise ValueError(
            f"Change request {change_request.pk} is not pending "
            f"(status={change_request.status})."
        )


@transaction.atomic
def apply_doctrine_payload(doctrine: EveDoctrine, payload: dict):
    _write_doctrine_history_if_needed(doctrine, payload)

    doctrine.name = payload["name"]
    doctrine.type = payload["type"]
    doctrine.description = payload["description"]
    if not doctrine.latest_version:
        doctrine.latest_version = str(uuid.uuid4())
    # A plain save restores a soft-deleted row. Keep it removed unless this
    # payload says to bring it back.
    doctrine.save_without_versioning(keep_deleted=True)
    if "retired" in payload:
        if payload["retired"]:
            if doctrine.deleted is None:
                doctrine.delete()
        elif doctrine.deleted is not None:
            doctrine.undelete()

    composition = _normalized_composition(payload.get("composition") or {})
    for role, fitting_ids in composition.items():
        for fitting_id in fitting_ids:
            EveDoctrineFitting.objects.get_or_create(
                doctrine=doctrine, fitting_id=fitting_id, role=role
            )

    for role in DOCTRINE_FITTING_ROLES:
        existing = EveDoctrineFitting.objects.filter(
            doctrine=doctrine, role=role
        )
        allowed = set(composition.get(role) or [])
        for link in existing:
            if link.fitting_id not in allowed:
                link.delete()

    doctrine.locations.set(payload.get("location_ids") or [])


def pending_doctrine_request_exists(
    doctrine: EveDoctrine,
) -> EveDoctrineChangeRequest | None:
    return (
        EveDoctrineChangeRequest.objects.filter(
            doctrine=doctrine,
            status=ChangeRequestStatus.PENDING,
        )
        .order_by("-submitted_at")
        .first()
    )


def submit_doctrine_change_request(
    doctrine: EveDoctrine,
    payload: dict,
    user,
    *,
    ensure_doctrine_row: bool = False,
    note: str = "",
) -> EveDoctrineChangeRequest | None:
    tier = change_tier_for(doctrine, payload)
    if tier is None:
        apply_doctrine_payload(doctrine, payload)
        return None

    if not can_propose_doctrine_change(user, tier):
        raise PermissionError(
            f"You need fittings.change_doctrine_{tier} to propose this change."
        )

    if ensure_doctrine_row and not doctrine.pk:
        doctrine.name = payload["name"]
        doctrine.type = payload["type"]
        doctrine.description = payload["description"]
        if not doctrine.latest_version:
            doctrine.latest_version = str(uuid.uuid4())
        doctrine.save_without_versioning()

    if doctrine.pk:
        existing = pending_doctrine_request_exists(doctrine)
        if existing:
            raise ValueError(
                f"A pending change request already exists (id={existing.pk})."
            )

    return EveDoctrineChangeRequest.objects.create(
        doctrine=doctrine,
        tier=tier,
        change_kind="full",
        payload=payload,
        submitted_by=user,
        submit_note=note.strip(),
    )


@transaction.atomic
def approve_doctrine_change_request(
    change_request: EveDoctrineChangeRequest,
    user,
    review_note: str = "",
) -> EveDoctrine:
    change_request = EveDoctrineChangeRequest.objects.select_for_update().get(
        pk=change_request.pk
    )
    _require_pending_change_request(change_request)
    validate_payload_matches_request_tier(
        change_request.doctrine, change_request.payload, change_request.tier
    )
    apply_doctrine_payload(change_request.doctrine, change_request.payload)
    change_request.status = ChangeRequestStatus.APPROVED
    change_request.reviewed_by = user
    change_request.reviewed_at = timezone.now()
    change_request.review_note = review_note or ""
    change_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        ]
    )
    return change_request.doctrine


@transaction.atomic
def reject_doctrine_change_request(
    change_request: EveDoctrineChangeRequest,
    user,
    review_note: str = "",
):
    change_request = EveDoctrineChangeRequest.objects.select_for_update().get(
        pk=change_request.pk
    )
    _require_pending_change_request(change_request)
    change_request.status = ChangeRequestStatus.REJECTED
    change_request.reviewed_by = user
    change_request.reviewed_at = timezone.now()
    change_request.review_note = review_note or ""
    change_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        ]
    )


@transaction.atomic
def cancel_doctrine_change_request(
    change_request: EveDoctrineChangeRequest,
    user,
):
    change_request = EveDoctrineChangeRequest.objects.select_for_update().get(
        pk=change_request.pk
    )
    _require_pending_change_request(change_request)
    change_request.status = ChangeRequestStatus.CANCELLED
    change_request.reviewed_by = user
    change_request.reviewed_at = timezone.now()
    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
