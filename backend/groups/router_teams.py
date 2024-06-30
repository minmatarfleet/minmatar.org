import logging
from typing import List, Optional

from django.utils import timezone
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer

from .models import Team, TeamRequest

logger = logging.getLogger(__name__)
router = Router(tags=["Groups"])


class ErrorResponse(BaseModel):
    detail: str


class TeamSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]
    directors: List[int] = []
    members: List[int] = []


@router.get(
    "",
    response=List[TeamSchema],
    description="List all available special interest groups",
)
def get_teams(request):
    teams = Team.objects.all()
    response = []
    for team in teams:
        response.append(
            TeamSchema(
                id=team.id,
                name=team.name,
                description=team.description,
                image_url=team.image_url,
                directors=[officer.id for officer in team.directors.all()],
                members=[member.id for member in team.members.all()],
            )
        )

    return response


@router.get(
    "/current",
    response=List[TeamSchema],
    auth=AuthBearer(),
    description="Get the special interest groups of the current user",
)
def get_current_teams(request, director: bool = False):
    teams = Team.objects.filter(members__id=request.user.id)
    if director:
        teams = Team.objects.filter(directors__id=request.user.id)
    response = []
    for team in teams:
        response.append(
            TeamSchema(
                id=team.id,
                name=team.name,
                description=team.description,
                image_url=team.image_url,
                directors=[officer.id for officer in team.directors.all()],
                members=[member.id for member in team.members.all()],
            )
        )
    return response


@router.get(
    "/{team_id}",
    response={200: TeamSchema, 404: ErrorResponse},
    description="Get a special interest group by id",
)
def get_team_by_id(request, team_id: int):
    team = Team.objects.filter(id=team_id).first()
    if not team:
        return 404, {"detail": "Team does not exist."}
    return TeamSchema(
        id=team.id,
        name=team.name,
        description=team.description,
        image_url=team.image_url,
        directors=[officer.id for officer in team.directors.all()],
        members=[member.id for member in team.members.all()],
    )


class TeamRequestSchema(BaseModel):
    id: int
    user: int
    team_id: int
    approved: Optional[bool]
    approved_by: Optional[int]
    approved_at: Optional[timezone.datetime] = None


@router.get(
    "/{team_id}/requests",
    response=List[TeamRequestSchema],
    auth=AuthBearer(),
    description="Get all requests to join a special interest group",
)
def get_team_requests(request, team_id: int):
    team_requests = TeamRequest.objects.filter(team__id=team_id)
    response = []
    for team_request in team_requests:
        response.append(
            TeamRequestSchema(
                id=team_request.id,
                user=team_request.user.id,
                team_id=team_request.team.id,
                approved=team_request.approved,
                approved_by=(
                    team_request.approved_by.id
                    if team_request.approved_by
                    else None
                ),
                approved_at=team_request.approved_at,
            )
        )
    return response


@router.post(
    "/{team_id}/requests",
    response={200: TeamRequestSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Request to join a special interest group",
)
def request_to_join_team(request, team_id: int):
    team = Team.objects.filter(id=team_id).first()
    if not request.user.has_perm("groups.add_teamrequest"):
        return 403, {
            "detail": "You do not have permission to request to join a team."
        }
    if not team:
        return 404, {"detail": "Team does not exist."}
    if TeamRequest.objects.filter(
        user=request.user, team=team, approved=None
    ).exists():
        return 404, {"detail": "Request already exists."}

    team_request = TeamRequest.objects.create(
        user=request.user, team=team, approved=None
    )
    return TeamRequestSchema(
        id=team_request.id,
        approved=False,
        approved_by=None,
        user=team_request.user.id,
        team_id=team_request.team.id,
    )


@router.post(
    "/{team_id}/requests/{request_id}/approve",
    response={200: TeamRequestSchema, 404: ErrorResponse, 403: ErrorResponse},
    auth=AuthBearer(),
    description="Approve a request to join a special interest group",
)
def approve_team_request(request, team_id: int, request_id: int):
    team = Team.objects.filter(id=team_id).first()
    if not team:
        return 404, {"detail": "Team does not exist."}

    if request.user not in team.directors.all() and not request.user.has_perm(
        "groups.change_team"
    ):
        return 403, {
            "detail": "You do not have permission to approve this request."
        }
    team_request = TeamRequest.objects.filter(id=request_id).first()
    if not team_request:
        return 404, {"detail": "Request does not exist."}
    team_request.approved = True
    team_request.approved_by = request.user
    team_request.save()
    return TeamRequestSchema(
        id=team_request.id,
        user=team_request.user.id,
        team_id=team_request.team.id,
        approved=team_request.approved,
        approved_by=team_request.approved_by.id,
    )


@router.post(
    "/{team_id}/requests/{request_id}/deny",
    response={200: TeamRequestSchema, 404: ErrorResponse, 403: ErrorResponse},
    auth=AuthBearer(),
    description="Deny a request to join a special interest group",
)
def deny_team_request(request, team_id: int, request_id: int):
    team = Team.objects.filter(id=team_id).first()
    if not team:
        return 404, {"detail": "Team does not exist."}

    if request.user not in team.directors.all() and not request.user.has_perm(
        "groups.change_team"
    ):
        return 403, {
            "detail": "You do not have permission to approve this request."
        }
    team_request = TeamRequest.objects.filter(id=request_id).first()
    if not team_request:
        return 404, {"detail": "Request does not exist."}
    team_request.approved = False
    team_request.approved_by = request.user
    team_request.approved_at = timezone.now()
    team_request.save()
    return TeamRequestSchema(
        id=team_request.id,
        user=team_request.user.id,
        team_id=team_request.team.id,
        approved=team_request.approved,
        approved_by=team_request.approved_by.id,
    )


@router.delete(
    "/{team_id}/members/{user_id}",
    response={200: TeamSchema, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Remove a member from a special interest group",
)
def remove_team_member(request, team_id: int, user_id: int):
    team = Team.objects.filter(id=team_id).first()
    if not team:
        return 404, {"detail": "Team does not exist."}

    if (
        request.user.id != user_id
        and request.user not in team.directors.all()
        and not request.user.has_perm("groups.change_team")
    ):
        return 403, {
            "detail": "You do not have permission to remove this member."
        }
    user = team.members.filter(id=user_id).first()
    if not user:
        return 404, {"detail": "User is not a member of this team."}
    team.members.remove(user)
    return TeamSchema(
        id=team.id,
        name=team.name,
        description=team.description,
        image_url=team.image_url,
        directors=[officer.id for officer in team.directors.all()],
        members=[member.id for member in team.members.all()],
    )
