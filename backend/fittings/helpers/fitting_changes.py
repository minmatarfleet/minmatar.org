"""Submit, apply, and publish fitting change requests."""

from django.db import transaction
from django.utils import timezone

from fittings.models import (
    ChangeRequestStatus,
    EVE_FITTING_VERSIONED_FIELDS,
    EVE_FITTING_VERSIONED_SCALAR_FIELDS,
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
        if field == "tags":
            current = fitting.tag_slugs()
        else:
            current = getattr(fitting, field)
        proposed = payload.get(field, current)
        if not _eve_fitting_versioned_field_equal(field, current, proposed):
            return True
    return False


def build_fitting_payload_from_instance(fitting: EveFitting) -> dict:
    payload = {}
    for field in EVE_FITTING_VERSIONED_FIELDS:
        if field == "tags":
            payload[field] = fitting.tag_slugs()
        else:
            payload[field] = getattr(fitting, field)
    return payload


def build_fitting_payload_from_form(
    form, original: EveFitting | None = None
) -> dict:
    """Proposed versioned values from admin form vs optional DB original."""
    payload = {}
    for field in EVE_FITTING_VERSIONED_FIELDS:
        if field in form.cleaned_data:
            value = form.cleaned_data[field]
            if field == "tags":
                payload[field] = list(value or [])
            else:
                payload[field] = value
        elif original is not None:
            if field == "tags":
                payload[field] = original.tag_slugs()
            else:
                payload[field] = getattr(original, field)
        else:
            if field == "tags":
                payload[field] = form.instance.tag_slugs()
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


def _name_from_eft_or_payload(payload: dict) -> str:
    eft = payload.get("eft_format") or ""
    return EveFitting.fitting_name_from_eft(eft) or payload.get("name") or ""


@transaction.atomic
def apply_fitting_payload(fitting: EveFitting, payload: dict):
    old_tags = fitting.tag_slugs()
    new_tags = EveFitting.coerce_tags(payload.get("tags", old_tags))
    version_before = fitting.latest_version

    for field in EVE_FITTING_VERSIONED_SCALAR_FIELDS:
        setattr(fitting, field, payload.get(field, getattr(fitting, field)))
    derived_name = EveFitting.fitting_name_from_eft(fitting.eft_format)
    if derived_name:
        fitting.name = derived_name
    fitting.save()

    scalar_bumped = fitting.latest_version != version_before
    fitting.set_tag_slugs(
        new_tags,
        write_history=not scalar_bumped,
    )


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
    name = _name_from_eft_or_payload(payload)
    if refit is None:
        EveFittingRefit.objects.create(
            base_fitting=base_fitting,
            name=name,
            eft_format=payload["eft_format"],
            description=payload.get("description", ""),
        )
        return
    refit.name = name
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


def _load_fitting_for_change_request(
    change_request: EveFittingChangeRequest,
) -> EveFitting:
    """Include soft-deleted rows (pending creates are soft-deleted until approved)."""
    return EveFitting.all_objects.select_for_update().get(
        pk=change_request.fitting_id
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
    fitting = _load_fitting_for_change_request(change_request)
    kind = change_request.change_kind
    payload = change_request.payload

    if kind == "fitting_create":
        if fitting.deleted:
            fitting.undelete()
        apply_fitting_payload(fitting, payload)
    elif kind == "fitting_versioned":
        apply_fitting_payload(fitting, payload)
    elif kind == "fitting_delete":
        fitting.delete()
    elif kind == "refit_create":
        apply_refit_payload(None, fitting, payload)
    elif kind == "refit_update":
        apply_refit_payload(change_request.refit, fitting, payload)
    elif kind == "refit_delete":
        apply_refit_payload(
            change_request.refit, fitting, payload, delete=True
        )
    else:
        raise ValueError(f"Unknown fitting change kind: {kind}")

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
