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
    TribeGroupChiefSeatSchema,
    TribeGroupSchema,
)
from tribes.endpoints.serialization import user_to_character_ref
from tribes.helpers import user_can_manage_group, user_can_view_group_roster
from tribes.helpers.chief_regions import LABELS as REGION_LABELS, REGIONS
from tribes.helpers.chiefs import (
    ChiefResolver,
    group_seats,
    user_is_executor,
)
from tribes.helpers.publishing import (
    KIND_EVENT,
    KIND_FLEET,
    KIND_POST,
    can_publish,
    group_role_name,
)
from tribes.models import (
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupMembership,
)


def _pending_region(request_user, tg: TribeGroup) -> str | None:
    """The seat the viewer volunteered for, if they have a pending offer."""
    offer = (
        TribeChiefVolunteer.objects.filter(
            tribe_group=tg,
            user_id=request_user.pk,
            status=TribeChiefVolunteer.STATUS_PENDING,
        )
        .values_list("region", flat=True)
        .first()
    )
    return offer


def serialize_chief_seats(
    tg: TribeGroup, show_identities: bool, pending_region: str | None = None
) -> list[TribeGroupChiefSeatSchema]:
    """Every timezone seat, US, EU, AU, filled or open."""
    by_region = {seat.region: seat for seat in group_seats(tg)}
    out = []
    for region in REGIONS:
        seat = by_region.get(region)
        out.append(
            TribeGroupChiefSeatSchema(
                region=region,
                label=REGION_LABELS[region],
                chief=(
                    user_to_character_ref(seat.user)
                    if seat is not None and show_identities
                    else None
                ),
                is_open=seat is None,
                has_volunteered=pending_region == region and seat is None,
            )
        )
    return out


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
    resolver: ChiefResolver | None = None,
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
    resolver = resolver or ChiefResolver()
    acting = resolver.for_group(tg)
    chief_ref = (
        user_to_character_ref(acting.user)
        if acting.user and not acting.is_interim and show_identities
        else None
    )
    # A hidden roster hides the group's own chief; a stand-in (tribe chief
    # or executor) is public on the tribe page anyway.
    acting_ref = (
        user_to_character_ref(acting.user)
        if acting.user and (show_identities or acting.is_interim)
        else None
    )
    can_apply = False
    can_manage = False
    can_appoint_chief = False
    has_volunteered = False
    pending_region = None
    if request_user is not None and getattr(
        request_user, "is_authenticated", False
    ):
        can_apply = can_use_feature(
            request_user, "tribes.apply", tribe_group=tg
        )
        can_manage = user_can_manage_group(request_user, tg)
        # A seat is open while any of the three timezones has no chief.
        if len(acting.users) < len(REGIONS) or acting.is_interim:
            can_appoint_chief = user_is_executor(request_user, resolver)
            pending_region = _pending_region(request_user, tg)
            has_volunteered = pending_region is not None

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
        chiefs=serialize_chief_seats(tg, show_identities, pending_region),
        acting_chief=acting_ref,
        chief_is_interim=acting.is_interim,
        can_appoint_chief=can_appoint_chief,
        can_set_chief=bool(getattr(request_user, "is_superuser", False)),
        has_volunteered=has_volunteered,
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
        fleets_enabled=bool(tg.fleets_enabled),
        events_enabled=bool(tg.events_enabled),
        effective_discord_channel_id=(
            str(tg.effective_discord_channel_id)
            if tg.effective_discord_channel_id
            else None
        ),
        discord_role_name=group_role_name(tg),
        **_viewer_flags(tg, request_user, member_group_ids, can_manage),
    )
