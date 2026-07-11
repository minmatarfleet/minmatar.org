"""Submit, apply, and publish fitting change requests."""

from django.db import transaction
from django.utils import timezone

from fittings.models import (
    ChangeRequestStatus,
    EVE_FITTING_VERSIONED_FIELDS,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingRefit,
    PROTECTION_TIER_NON_STRATEGIC,
    _eve_fitting_versioned_field_equal,
)
from fittings.helpers.permissions import (
    can_propose_fitting_change,
    effective_protection_tier,
)


def fitting_change_request_tier(fitting: EveFitting) -> str:
    """Tier for fitting approvals; unlinked fittings use non_strategic."""
    return effective_protection_tier(fitting) or PROTECTION_TIER_NON_STRATEGIC


def fitting_payload_changed(fitting: EveFitting, payload: dict) -> bool:
    for field in EVE_FITTING_VERSIONED_FIELDS:
        current = getattr(fitting, field)
        proposed = payload.get(field, current)
        if not _eve_fitting_versioned_field_equal(field, current, proposed):
            return True
    return False


def build_fitting_payload_from_instance(fitting: EveFitting) -> dict:
    return {
        field: getattr(fitting, field)
        for field in EVE_FITTING_VERSIONED_FIELDS
    }


def build_fitting_payload_from_form(
    form, original: EveFitting | None = None
) -> dict:
    """Proposed versioned values from admin form vs optional DB original."""
    payload = {}
    for field in EVE_FITTING_VERSIONED_FIELDS:
        if field in form.cleaned_data:
            payload[field] = form.cleaned_data[field]
        elif original is not None:
            payload[field] = getattr(original, field)
        else:
            payload[field] = getattr(form.instance, field)
    return payload


def build_refit_payload(refit: EveFittingRefit) -> dict:
    return {
        "name": refit.name,
        "eft_format": refit.eft_format,
        "description": refit.description or "",
    }


def pending_fitting_request_exists(
    fitting: EveFitting,
) -> EveFittingChangeRequest | None:
    return (
        EveFittingChangeRequest.objects.filter(
            fitting=fitting,
            status=ChangeRequestStatus.PENDING,
        )
        .order_by("-submitted_at")
        .first()
    )


@transaction.atomic
def apply_fitting_payload(fitting: EveFitting, payload: dict):
    for field in EVE_FITTING_VERSIONED_FIELDS:
        setattr(fitting, field, payload.get(field, getattr(fitting, field)))
    fitting.save()


@transaction.atomic
def apply_refit_payload(
    refit: EveFittingRefit | None,
    base_fitting: EveFitting,
    payload: dict,
    *,
    delete: bool = False,
):
    if delete and refit and refit.pk:
        refit.delete()
        return
    if refit is None:
        EveFittingRefit.objects.create(
            base_fitting=base_fitting,
            name=payload["name"],
            eft_format=payload["eft_format"],
            description=payload.get("description", ""),
        )
        return
    refit.name = payload["name"]
    refit.eft_format = payload["eft_format"]
    refit.description = payload.get("description", "")
    refit.save()


def submit_fitting_change_request(
    fitting: EveFitting,
    *,
    change_kind: str,
    payload: dict,
    user,
    refit=None,
) -> EveFittingChangeRequest | None:
    tier = fitting_change_request_tier(fitting)

    if not can_propose_fitting_change(user, tier):
        raise PermissionError(
            f"You need fittings.change_doctrine_fitting_{tier} to propose this change."
        )

    existing = pending_fitting_request_exists(fitting)
    if existing:
        raise ValueError(
            f"A pending change request already exists (id={existing.pk})."
        )

    return EveFittingChangeRequest.objects.create(
        fitting=fitting,
        refit=refit,
        tier=tier,
        change_kind=change_kind,
        payload=payload,
        submitted_by=user,
    )


def _require_pending_change_request(change_request) -> None:
    if change_request.status != ChangeRequestStatus.PENDING:
        raise ValueError(
            f"Change request {change_request.pk} is not pending "
            f"(status={change_request.status})."
        )


@transaction.atomic
def approve_fitting_change_request(
    change_request: EveFittingChangeRequest,
    user,
    review_note: str = "",
):
    change_request = EveFittingChangeRequest.objects.select_for_update().get(
        pk=change_request.pk
    )
    _require_pending_change_request(change_request)
    fitting = change_request.fitting
    kind = change_request.change_kind
    payload = change_request.payload

    if kind == "fitting_versioned":
        apply_fitting_payload(fitting, payload)
    elif kind == "refit_create":
        apply_refit_payload(None, fitting, payload)
    elif kind == "refit_update":
        apply_refit_payload(change_request.refit, fitting, payload)
    elif kind == "refit_delete":
        apply_refit_payload(
            change_request.refit, fitting, payload, delete=True
        )

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


@transaction.atomic
def reject_fitting_change_request(
    change_request: EveFittingChangeRequest,
    user,
    review_note: str = "",
):
    change_request = EveFittingChangeRequest.objects.select_for_update().get(
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
def cancel_fitting_change_request(
    change_request: EveFittingChangeRequest,
    user,
):
    change_request = EveFittingChangeRequest.objects.select_for_update().get(
        pk=change_request.pk
    )
    _require_pending_change_request(change_request)
    change_request.status = ChangeRequestStatus.CANCELLED
    change_request.reviewed_by = user
    change_request.reviewed_at = timezone.now()
    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
