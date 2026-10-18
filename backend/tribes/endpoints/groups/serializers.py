"""Serialize TribeGroup rows for list/detail endpoints."""

from groups.helpers.feature_access import (
    can_use_feature,
    tribe_group_effective_affiliation_ids,
)
from groups.models import AffiliationType
from tribes.endpoints.groups.rank_serializers import (
    serialize_tribe_group_ranks,
)
from tribes.endpoints.groups.schemas import (
    AffiliationRefSchema,
    QualifyingAssetTypeSchema,
    QualifyingSkillSchema,
    RequirementSchema,
    TribeGroupSchema,
)
from tribes.endpoints.serialization import user_to_character_ref
from tribes.helpers import user_can_manage_group, user_can_view_group_roster
from tribes.helpers.publishing import (
    KIND_EVENT,
    KIND_FLEET,
    KIND_POST,
    can_publish,
    group_role_name,
)
from tribes.models import TribeGroup, TribeGroupMembership


def effective_allowed_affiliations(
    tribe_group: TribeGroup,
) -> list[AffiliationRefSchema]:
    affiliation_ids = tribe_group_effective_affiliation_ids(
        tribe_group,
        feature_code="tribes.apply",
    )
    if not affiliation_ids:
        return []
    rows = AffiliationType.objects.filter(pk__in=affiliation_ids).order_by(
        "name"
    )
    return [AffiliationRefSchema(id=a.pk, name=a.name) for a in rows]


def _viewer_flags(
    tg: TribeGroup, user, member_group_ids, manages: bool
) -> dict:
    """is_member and the can_* publishing flags for this viewer."""
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    if member_group_ids is None:
        is_member = TribeGroupMembership.objects.filter(
            user_id=user.pk,
            tribe_group=tg,
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).exists()
    else:
        is_member = tg.pk in member_group_ids

    def allowed(kind):
        return can_publish(
            user, tg, kind, is_member=is_member, manages=manages
        )

    return {
        "is_member": is_member,
        "can_post": allowed(KIND_POST),
        "can_schedule_fleets": allowed(KIND_FLEET),
        "can_create_events": allowed(KIND_EVENT),
    }


def serialize_tribe_group(
    tg: TribeGroup,
    *,
    request_user=None,
    member_count: int | None = None,
    member_group_ids=None,
) -> TribeGroupSchema:
    """``member_group_ids``: the viewer's active group ids, when a list
    endpoint already loaded them."""
    if member_count is None:
        member_count = TribeGroupMembership.objects.filter(
            tribe_group=tg, status=TribeGroupMembership.STATUS_ACTIVE
        ).count()
    show_identities = not tg.roster_hidden or (
        request_user is not None
        and user_can_view_group_roster(request_user, tg)
    )
    chief_ref = (
        user_to_character_ref(tg.chief)
        if tg.chief and show_identities
        else None
    )
    can_apply = False
    can_manage = False
    if request_user is not None and getattr(
        request_user, "is_authenticated", False
    ):
        can_apply = can_use_feature(
            request_user, "tribes.apply", tribe_group=tg
        )
        can_manage = user_can_manage_group(request_user, tg)

    return TribeGroupSchema(
        id=tg.pk,
        tribe_id=tg.tribe_id,
        tribe_name=tg.tribe.name,
        name=tg.name,
        code=tg.code or "",
        description=tg.description,
        content=tg.content or "",
        discord_channel_id=tg.discord_channel_id,
        chief=chief_ref,
        is_active=tg.is_active,
        member_count=member_count,
        requirements=[
            RequirementSchema(
                id=req.pk,
                asset_types=[
                    QualifyingAssetTypeSchema(
                        type_id=at.eve_type_id,
                        type_name=at.eve_type.name if at.eve_type else "",
                        location_ids=list(
                            at.locations.values_list("location_id", flat=True)
                        ),
                    )
                    for at in req.asset_types.all()
                    if at.eve_type_id
                ],
                qualifying_skills=[
                    QualifyingSkillSchema(
                        skill_type_id=s.eve_type_id,
                        skill_name=s.eve_type.name if s.eve_type else "",
                        minimum_level=s.minimum_level,
                    )
                    for s in req.qualifying_skills.all()
                    if s.eve_type_id
                ],
            )
            for req in tg.requirements.all()
        ],
        ranks=serialize_tribe_group_ranks(tg),
        required_token_type=tg.required_token_type or None,
        require_off_trial=bool(tg.require_off_trial),
        allowed_affiliations=effective_allowed_affiliations(tg),
        can_apply=can_apply,
        can_manage=can_manage,
        roster_hidden=bool(tg.roster_hidden),
        allow_alliance_posts=bool(tg.allow_alliance_posts),
        allow_open_fleets=bool(tg.allow_open_fleets),
        effective_discord_channel_id=tg.effective_discord_channel_id,
        discord_role_name=group_role_name(tg),
        **_viewer_flags(tg, request_user, member_group_ids, can_manage),
    )
