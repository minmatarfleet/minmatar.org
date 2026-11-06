"""Corporation recruitment requirements: public list, my checks, the CEO
editor and the recruiter's view of an application."""

from typing import Dict, List, Optional

from ninja import Router, Schema

from alliance.helpers.trial_peers import corp_trial_length
from alliance.helpers.trial_report import latest_payload
from app.errors import ErrorResponse
from authentication import AuthBearer
from applications.models import (
    CorporationRequirement,
    EveCorporationApplication,
)
from applications.requirements import rules as R
from applications.requirements import services as S
from applications.requirements.evaluate import account_counts
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.models import EveCorporation
from groups.helpers.feature_access import can_use_feature

router = Router(tags=["Applications"])


class RequirementRule(Schema):
    id: int
    kind: str
    params: Dict
    who: str
    importance: str
    position: int
    text: str


class ManagedRequirementRule(RequirementRule):
    members_pass: Optional[int] = None


class RequirementCheck(Schema):
    id: int
    kind: str
    importance: str
    text: str
    status: str
    detail: str
    ship_type_ids: List[int]
    training_days: Optional[float] = None


class CorporationRequirements(Schema):
    corporation_id: int
    rules: List[RequirementRule]
    interview_topics: List[str]
    trial_days: Optional[int] = None


class MyCorporationRequirements(Schema):
    corporation_id: int
    checks: List[RequirementCheck]
    interview_topics: List[str]
    can_apply: bool
    characters: int
    accounts: Optional[int] = None


class RequirementDoctrineOption(Schema):
    id: int
    name: str


class RequirementCapabilityOption(Schema):
    key: str
    label: str


class RequirementOptions(Schema):
    doctrines: List[RequirementDoctrineOption]
    capabilities: List[RequirementCapabilityOption]
    brackets: List[str]


class ManagedCorporationRequirements(Schema):
    corporation_id: int
    rules: List[ManagedRequirementRule]
    interview_topics: List[str]
    members: int
    max_rules: int
    options: RequirementOptions


class RequirementCreateRequest(Schema):
    kind: str
    params: Dict = {}
    who: str = CorporationRequirement.WHO_ANY
    importance: str = CorporationRequirement.IMPORTANCE_PREFERRED


class RequirementUpdateRequest(Schema):
    params: Optional[Dict] = None
    who: Optional[str] = None
    importance: Optional[str] = None


class InterviewTopicsRequest(Schema):
    topics: List[str]


class InterviewTopicsResponse(Schema):
    interview_topics: List[str]


class ApplicationRequirements(Schema):
    application_id: int
    checks: List[RequirementCheck]
    required_met: int
    required_total: int
    preferred_met: int
    preferred_total: int


def _corporation(corporation_id: int) -> EveCorporation | None:
    return EveCorporation.objects.filter(corporation_id=corporation_id).first()


def _trial_days(corporation_id: int) -> int | None:
    length = corp_trial_length(latest_payload(), corporation_id)
    days = (length or {}).get("days")
    return round(days) if days else None


def _editable(request, corporation_id: int):
    corporation = _corporation(corporation_id)
    if corporation is None:
        return None, (404, ErrorResponse(detail="Corporation not found"))
    if not can_edit_corporation_settings(request.user, corporation):
        return None, (403, ErrorResponse(detail="Not authorised"))
    return corporation, None


@router.get(
    "/corporations/{corporation_id}/requirements",
    summary="A corporation's recruitment requirements and interview topics",
    response={200: CorporationRequirements, 404: ErrorResponse},
)
def get_corporation_requirements(request, corporation_id: int):
    corporation = _corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    return {
        "corporation_id": corporation_id,
        "rules": S.rule_dicts(S.corporation_rules(corporation)),
        "interview_topics": S.interview_topics(corporation),
        "trial_days": _trial_days(corporation_id),
    }


@router.get(
    "/corporations/{corporation_id}/requirements/me",
    summary="The caller's characters checked against a corporation's requirements",
    auth=AuthBearer(),
    response={200: MyCorporationRequirements, 404: ErrorResponse},
)
def get_my_corporation_requirements(request, corporation_id: int):
    corporation = _corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    checks = S.checks_for(corporation, request.user.id)
    characters, accounts = account_counts(request.user.id)
    return {
        "corporation_id": corporation_id,
        "checks": [check.as_dict() for check in checks],
        "interview_topics": S.interview_topics(corporation),
        "can_apply": not any(check.blocks for check in checks),
        "characters": characters,
        "accounts": accounts,
    }


@router.get(
    "/corporations/{corporation_id}/requirements/manage",
    summary="Requirements with member pass rates, for the corp's Settings tab",
    auth=AuthBearer(),
    response={
        200: ManagedCorporationRequirements,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_managed_corporation_requirements(request, corporation_id: int):
    corporation, error = _editable(request, corporation_id)
    if error:
        return error
    rules = S.corporation_rules(corporation)
    scores = S.member_pass_rates(corporation, rules)
    rows = []
    for row in S.rule_dicts(rules):
        row["members_pass"] = scores["rates"].get(row["id"])
        rows.append(row)
    return {
        "corporation_id": corporation_id,
        "rules": rows,
        "interview_topics": S.interview_topics(corporation),
        "members": scores["members"],
        "max_rules": R.MAX_RULES_PER_CORPORATION,
        "options": R.rule_options(),
    }


@router.post(
    "/corporations/{corporation_id}/requirements",
    summary="Add a recruitment requirement (CEO)",
    auth=AuthBearer(),
    response={
        200: RequirementRule,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def create_corporation_requirement(
    request, corporation_id: int, payload: RequirementCreateRequest
):
    corporation, error = _editable(request, corporation_id)
    if error:
        return error
    try:
        rule = S.create_rule(
            corporation,
            request.user,
            payload.kind,
            payload.params,
            payload.who,
            payload.importance,
        )
    except R.RuleError as e:
        return 400, ErrorResponse(detail=str(e))
    return S.rule_dicts([rule])[0]


@router.patch(
    "/corporations/{corporation_id}/requirements/{requirement_id}",
    summary="Change a recruitment requirement (CEO)",
    auth=AuthBearer(),
    response={
        200: RequirementRule,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def update_corporation_requirement(
    request,
    corporation_id: int,
    requirement_id: int,
    payload: RequirementUpdateRequest,
):
    corporation, error = _editable(request, corporation_id)
    if error:
        return error
    rule = CorporationRequirement.objects.filter(
        corporation=corporation, pk=requirement_id
    ).first()
    if rule is None:
        return 404, ErrorResponse(detail="Requirement not found")
    try:
        S.update_rule(
            rule,
            params=payload.params,
            who=payload.who,
            importance=payload.importance,
        )
    except R.RuleError as e:
        return 400, ErrorResponse(detail=str(e))
    return S.rule_dicts([rule])[0]


@router.delete(
    "/corporations/{corporation_id}/requirements/{requirement_id}",
    summary="Remove a recruitment requirement (CEO)",
    auth=AuthBearer(),
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
)
def delete_corporation_requirement(
    request, corporation_id: int, requirement_id: int
):
    corporation, error = _editable(request, corporation_id)
    if error:
        return error
    deleted, _ = CorporationRequirement.objects.filter(
        corporation=corporation, pk=requirement_id
    ).delete()
    if not deleted:
        return 404, ErrorResponse(detail="Requirement not found")
    return 204, None


@router.put(
    "/corporations/{corporation_id}/interview-topics",
    summary="Set the topics recruiters ask about in the interview (CEO)",
    auth=AuthBearer(),
    response={
        200: InterviewTopicsResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def put_corporation_interview_topics(
    request, corporation_id: int, payload: InterviewTopicsRequest
):
    corporation, error = _editable(request, corporation_id)
    if error:
        return error
    S.save_interview_topics(corporation, payload.topics)
    return {"interview_topics": S.interview_topics(corporation)}


@router.get(
    "/corporations/{corporation_id}/applications/{application_id}/requirements",
    summary="How an application's applicant meets the corporation's requirements",
    auth=AuthBearer(),
    response={
        200: ApplicationRequirements,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_application_requirements(
    request, corporation_id: int, application_id: int
):
    application = EveCorporationApplication.objects.filter(
        corporation_id=corporation_id, id=application_id
    ).first()
    corporation = _corporation(corporation_id)
    if application is None or corporation is None:
        return 404, ErrorResponse(detail="Application not found.")
    is_applicant = application.user_id == request.user.id
    if not is_applicant and not can_use_feature(
        request.user, "applications.view"
    ):
        return 403, ErrorResponse(
            detail="You do not have permission to view this application."
        )
    checks = S.checks_for(corporation, application.user_id)
    required = [
        c
        for c in checks
        if c.importance == CorporationRequirement.IMPORTANCE_REQUIRED
    ]
    preferred = [c for c in checks if c not in required]
    return {
        "application_id": application.id,
        "checks": [check.as_dict() for check in checks],
        "required_met": sum(c.status == "met" for c in required),
        "required_total": len(required),
        "preferred_met": sum(c.status == "met" for c in preferred),
        "preferred_total": len(preferred),
    }
