import logging
from typing import List, Optional

from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer

from .models import Sig, SigRequest

logger = logging.getLogger(__name__)
router = Router(tags=["Groups"])


class ErrorResponse(BaseModel):
    detail: str


class SigSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]
    officers: List[int] = []
    members: List[int] = []


@router.get(
    "",
    response=List[SigSchema],
    description="List all available special interest groups",
)
async def get_sigs(request):
    sigs = Sig.objects.all()
    response = []
    for sig in sigs:
        response.append(
            SigSchema(
                id=sig.id,
                name=sig.name,
                description=sig.description,
                image_url=sig.image_url,
                officers=[officer.id for officer in sig.officers.all()],
                members=[member.id for member in sig.members.all()],
            )
        )

    return response


@router.get(
    "/current",
    response=List[SigSchema],
    auth=AuthBearer(),
    description="Get the special interest groups of the current user",
)
async def get_current_sigs(request):
    sigs = Sig.objects.filter(members__id=request.user.id)
    response = []
    for sig in sigs:
        response.append(
            SigSchema(
                id=sig.id,
                name=sig.name,
                description=sig.description,
                image_url=sig.image_url,
                officers=[officer.id for officer in sig.officers.all()],
                members=[member.id for member in sig.members.all()],
            )
        )
    return response


@router.get(
    "/{sig_id}",
    response={200: SigSchema, 404: ErrorResponse},
    description="Get a special interest group by id",
)
async def get_sig_by_id(request, sig_id: int):
    sig = Sig.objects.filter(id=sig_id).first()
    if not sig:
        return 404, {"detail": "Sig does not exist."}
    return SigSchema(
        id=sig.id,
        name=sig.name,
        description=sig.description,
        image_url=sig.image_url,
        officers=[officer.id for officer in sig.officers.all()],
        members=[member.id for member in sig.members.all()],
    )


class SigRequestSchema(BaseModel):
    id: int
    user: int
    sig_id: int
    approved: Optional[bool]
    approved_by: Optional[int]


@router.get(
    "/{sig_id}/requests",
    response=List[SigRequestSchema],
    auth=AuthBearer(),
    description="Get all requests to join a special interest group",
)
async def get_sig_requests(request, sig_id: int):
    sig_requests = SigRequest.objects.filter(sig__id=sig_id)
    response = []
    for sig_request in sig_requests:
        response.append(
            SigRequestSchema(
                id=sig_request.id,
                user=sig_request.user.id,
                sig_id=sig_request.sig.id,
                approved=sig_request.approved,
                approved_by=(
                    sig_request.approved_by.id
                    if sig_request.approved_by
                    else None
                ),
            )
        )
    return response


@router.post(
    "/{sig_id}/requests",
    response={200: SigRequestSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Request to join a special interest group",
)
async def request_to_join_sig(request, sig_id: int):
    sig = Sig.objects.filter(id=sig_id).first()
    if not sig:
        return 404, {"detail": "Sig does not exist."}
    if SigRequest.objects.filter(user=request.user, sig=sig).exists():
        return 404, {"detail": "Request already exists."}

    sig_request = SigRequest.objects.create(
        user=request.user, sig=sig, approved=None
    )
    return SigRequestSchema(
        id=sig_request.id,
        user=sig_request.user.id,
        sig_id=sig_request.sig.id,
    )


@router.post(
    "/{sig_id}/requests/{request_id}/approve",
    response={200: SigRequestSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Approve a request to join a special interest group",
)
async def approve_sig_request(request, sig_id: int, request_id: int):
    sig = Sig.objects.filter(id=sig_id).first()
    if not sig:
        return 404, {"detail": "Sig does not exist."}

    if request.user not in sig.officers.all() and not request.user.has_perm(
        "groups.change_sig"
    ):
        return 403, {
            "detail": "You do not have permission to approve this request."
        }
    sig_request = SigRequest.objects.filter(id=request_id).first()
    if not sig_request:
        return 404, {"detail": "Request does not exist."}
    sig_request.approved = True
    sig_request.approved_by = request.user
    sig_request.save()
    return SigRequestSchema(
        id=sig_request.id,
        user=sig_request.user.id,
        sig_id=sig_request.sig.id,
        approved=sig_request.approved,
        approved_by=sig_request.approved_by.id,
    )


@router.post(
    "/{sig_id}/requests/{request_id}/deny",
    response={200: SigRequestSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Deny a request to join a special interest group",
)
async def deny_sig_request(request, sig_id: int, request_id: int):
    sig = Sig.objects.filter(id=sig_id).first()
    if not sig:
        return 404, {"detail": "Sig does not exist."}

    if request.user not in sig.officers.all() and not request.user.has_perm(
        "groups.change_sig"
    ):
        return 403, {
            "detail": "You do not have permission to approve this request."
        }
    sig_request = SigRequest.objects.filter(id=request_id).first()
    if not sig_request:
        return 404, {"detail": "Request does not exist."}
    sig_request.approved = False
    sig_request.approved_by = request.user
    sig_request.save()
    return SigRequestSchema(
        id=sig_request.id,
        user=sig_request.user.id,
        sig_id=sig_request.sig.id,
        approved=sig_request.approved,
        approved_by=sig_request.approved_by.id,
    )


@router.delete(
    "/{sig_id}/members/{user_id}",
    response={200: SigSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Remove a user from a special interest group",
)
async def remove_sig_member(request, sig_id: int, user_id: int):
    sig = Sig.objects.filter(id=sig_id).first()
    if not sig:
        return 404, {"detail": "Sig does not exist."}

    if request.user not in sig.officers.all() and not request.user.has_perm(
        "groups.change_sig"
    ):
        return 403, {
            "detail": "You do not have permission to remove this user."
        }
    user = sig.members.filter(id=user_id).first()
    if not user:
        return 404, {"detail": "User does not exist."}
    sig.members.remove(user)
    return SigSchema(
        id=sig.id,
        name=sig.name,
        description=sig.description,
        image_url=sig.image_url,
        officers=[officer.id for officer in sig.officers.all()],
        members=[member.id for member in sig.members.all()],
    )
