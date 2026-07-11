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
    composition_snapshot_for_doctrine,
    location_ids_for_doctrine,
)
from fittings.helpers.permissions import (
    can_propose_doctrine_change,
    protection_tier_for_doctrine,
    protection_tier_for_doctrine_type,
)


def build_doctrine_payload_from_form(cleaned_data) -> dict:
    return {
        "name": cleaned_data["name"],
        "type": cleaned_data["type"],
        "description": cleaned_data["description"],
        "composition": {
            "primary": sorted(
                f.pk for f in cleaned_data.get("primary_fittings", [])
            ),
            "secondary": sorted(
                f.pk for f in cleaned_data.get("secondary_fittings", [])
            ),
            "support": sorted(
                f.pk for f in cleaned_data.get("support_fittings", [])
            ),
        },
        "location_ids": sorted(
            loc.pk for loc in cleaned_data.get("locations", [])
        ),
    }


def _normalized_composition(comp: dict) -> dict:
    return {
        "primary": sorted(comp.get("primary") or []),
        "secondary": sorted(comp.get("secondary") or []),
        "support": sorted(comp.get("support") or []),
    }


def doctrine_state_changed(doctrine: EveDoctrine, payload: dict) -> bool:
    if (doctrine.name, doctrine.type, doctrine.description) != (
        payload["name"],
        payload["type"],
        payload["description"],
    ):
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


def _write_doctrine_history_if_needed(doctrine: EveDoctrine, payload: dict):
    if not doctrine.pk or not doctrine.latest_version:
        return
    if not doctrine_state_changed(doctrine, payload):
        return
    EveDoctrineHistory.objects.create(
        doctrine=doctrine,
        superseded_version_id=doctrine.latest_version,
        name=doctrine.name,
        type=doctrine.type,
        description=doctrine.description,
        composition=composition_snapshot_for_doctrine(doctrine),
        location_ids=location_ids_for_doctrine(doctrine),
    )
    doctrine.latest_version = str(uuid.uuid4())


def validate_payload_matches_request_tier(payload: dict, tier: str) -> None:
    """Ensure approved payload cannot downgrade protection tier (SEC-2)."""
    payload_tier = protection_tier_for_doctrine_type(payload.get("type", ""))
    if payload_tier != tier:
        raise ValueError(
            f"Payload doctrine type '{payload.get('type')}' does not match "
            f"request tier '{tier}'."
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
    doctrine.save_without_versioning()

    composition = _normalized_composition(payload.get("composition") or {})
    for role, fitting_ids in composition.items():
        for fitting_id in fitting_ids:
            EveDoctrineFitting.objects.get_or_create(
                doctrine=doctrine, fitting_id=fitting_id, role=role
            )

    for role in ("primary", "secondary", "support"):
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
) -> EveDoctrineChangeRequest | None:
    tier = protection_tier_for_doctrine(doctrine)
    if tier is None:
        apply_doctrine_payload(doctrine, payload)
        return None

    if not can_propose_doctrine_change(user, tier):
        raise PermissionError(
            f"You need fittings.change_doctrine_{tier} to propose this change."
        )

    existing = pending_doctrine_request_exists(doctrine)
    if existing:
        raise ValueError(
            f"A pending change request already exists (id={existing.pk})."
        )

    if ensure_doctrine_row and not doctrine.pk:
        doctrine.name = payload["name"]
        doctrine.type = payload["type"]
        doctrine.description = payload["description"]
        if not doctrine.latest_version:
            doctrine.latest_version = str(uuid.uuid4())
        doctrine.save_without_versioning()

    return EveDoctrineChangeRequest.objects.create(
        doctrine=doctrine,
        tier=tier,
        change_kind="full",
        payload=payload,
        submitted_by=user,
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
        change_request.payload, change_request.tier
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
