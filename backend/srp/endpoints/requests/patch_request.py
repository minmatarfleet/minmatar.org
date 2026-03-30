"""PATCH /{int:request_id} — update SRP request status."""

from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.requests.helpers import can_update
from srp.endpoints.requests.schemas import SrpPatchResult, UpdateSrpRequest
from srp.helpers import send_decision_notification
from srp.models import EveFleetShipReimbursement

PATH = "/{int:request_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: SrpPatchResult, 403: ErrorResponse, 404: ErrorResponse},
    "description": (
        "Update an SRP request. Owners may withdraw; "
        "srp.change_evefleetshipreimbursement may set any status."
    ),
}


def patch_srp_request(request, request_id: int, payload: UpdateSrpRequest):
    reimbursement = EveFleetShipReimbursement.objects.filter(
        id=request_id
    ).first()

    if not reimbursement:
        return 404, {"detail": "Reimbursement does not exist"}

    if not can_update(request.user, reimbursement):
        return 403, {
            "detail": "User missing permission srp.change_evefleetshipreimbursement"
        }

    if not request.user.has_perm("srp.change_evefleetshipreimbursement"):
        if payload.status != "withdrawn":
            return 403, {"detail": "Permission denied"}

    old_status = reimbursement.status
    reimbursement.status = payload.status
    if payload.status == "approved" and old_status != "approved":
        reimbursement.approved_at = timezone.now()
    reimbursement.save()

    if reimbursement.status in ["approved", "rejected"]:
        try:
            send_decision_notification(reimbursement)
            mail_result = "Success"
        except Exception as err:
            mail_result = f"Error sending mail: {err}"
    else:
        mail_result = "N/A"

    return SrpPatchResult(
        database_update_status="Success",
        evemail_status=mail_result,
    )
