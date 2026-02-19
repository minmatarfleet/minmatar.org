import logging

from datetime import datetime
from typing import List, Optional

from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.models import EveCharacter, EveCorporation

from .models import EveCorporationApplication

router = Router(tags=["Applications"])
logger = logging.getLogger(__name__)


class CorporationApplicationResponse(BaseModel):
    status: str
    application_id: int
    user_id: int
    corporation_id: int


class CorporationApplicationCharacterResponse(BaseModel):
    character_id: int
    character_name: str


class CorporationApplicationDetailResponse(CorporationApplicationResponse):
    description: str
    created_at: datetime
    updated_at: datetime
    characters: List[CorporationApplicationCharacterResponse]
    discord_thread: Optional[int]


class CorporationApplicationRequest(BaseModel):
    description: str


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/corporations/{corporation_id}/applications",
    summary="Get corporation applications",
    auth=AuthBearer(),
    response={200: List[CorporationApplicationResponse], 403: ErrorResponse},
)
def get_corporation_applications(request, corporation_id: int):
    applications = EveCorporationApplication.objects.filter(
        corporation_id=corporation_id
    )
    response = []
    for application in applications:
        response.append(
            {
                "status": application.status,
                "user_id": application.user.id,
                "corporation_id": application.corporation_id,
                "application_id": application.id,
            }
        )
    return response


@router.post(
    "/corporations/{corporation_id}/applications",
    summary="Create a corporation application",
    auth=AuthBearer(),
    response={200: CorporationApplicationResponse, 404: ErrorResponse},
)
def create_corporation_application(
    request, corporation_id: int, payload: CorporationApplicationRequest
):
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        return 404, {"detail": "Corporation not found."}

    application = EveCorporationApplication.objects.create(
        corporation_id=corporation_id,
        user_id=request.user.id,
        description=payload.description,
    )

    logger.info(
        "Application to %s submitted by %s",
        corporation.name,
        request.user.username,
    )

    return 200, {
        "status": application.status,
        "user_id": application.user.id,
        "corporation_id": application.corporation_id,
        "application_id": application.id,
    }


@router.get(
    "/corporations/{corporation_id}/applications/{application_id}",
    summary="Get a corporation application by ID",
    auth=AuthBearer(),
    response={
        200: CorporationApplicationDetailResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_corporation_application_by_id(
    request, corporation_id: int, application_id: int
):
    application = EveCorporationApplication.objects.filter(
        corporation_id=corporation_id, id=application_id
    ).first()
    if not application:
        return 404, ErrorResponse(detail="Application not found.")
    is_applicant = application.user_id == request.user.id
    has_view_perm = request.user.has_perm(
        "applications.view_evecorporationapplication"
    )
    if not is_applicant and not has_view_perm:
        return 403, ErrorResponse(
            detail="You do not have permission to view this application."
        )
    characters = EveCharacter.objects.filter(token__user=application.user)
    character_list = [
        {
            "character_id": c.character_id,
            "character_name": c.character_name,
        }
        for c in characters
    ]
    return {
        "status": application.status,
        "application_id": application.id,
        "user_id": application.user.id,
        "corporation_id": application.corporation_id,
        "description": application.description,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "discord_thread": application.discord_thread_id,
        "characters": character_list,
    }


@router.post(
    "/corporations/{corporation_id}/applications/{application_id}/accept",
    summary="Accept a corporation application",
    auth=AuthBearer(),
    response={
        200: CorporationApplicationResponse,
        403: ErrorResponse,
    },
)
def accept_corporation_application(
    request, corporation_id: int, application_id: int
):
    if not request.user.has_perm(
        "applications.change_evecorporationapplication"
    ):
        return 403, {
            "detail": "You do not have permission to accept applications."
        }
    application = EveCorporationApplication.objects.get(
        corporation_id=corporation_id, id=application_id
    )
    application.status = "accepted"
    application.processed_by = request.user
    application.save()

    logger.info(
        "Application for %s accepted by %s",
        application.user.username,
        request.user.username,
    )

    return {
        "status": application.status,
        "user_id": application.user.id,
        "corporation_id": application.corporation_id,
        "application_id": application.id,
    }


@router.post(
    "/corporations/{corporation_id}/applications/{application_id}/reject",
    summary="Reject a corporation application",
    auth=AuthBearer(),
    response={
        200: CorporationApplicationResponse,
        403: ErrorResponse,
    },
)
def reject_corporation_application(
    request, corporation_id: int, application_id: int
):
    if not request.user.has_perm(
        "applications.change_evecorporationapplication"
    ):
        return 403, {
            "detail": "You do not have permission to accept applications."
        }
    application = EveCorporationApplication.objects.get(
        corporation_id=corporation_id, id=application_id
    )
    application.status = "rejected"
    application.processed_by = request.user
    application.save()

    logger.info(
        "Application for %s rejected by %s",
        application.user.username,
        request.user.username,
    )

    return {
        "status": application.status,
        "user_id": application.user.id,
        "corporation_id": application.corporation_id,
        "application_id": application.id,
    }
