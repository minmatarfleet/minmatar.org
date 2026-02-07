from django.contrib.auth.models import Group as AuthGroup
from django.contrib.auth.models import User

from eveonline.models import EveCorporation
from users.helpers import offboard_group

from .models import EveCorporationGroup, Team

PEOPLE_TEAM = "People Team"
TECH_TEAM = "Technology Team"

# Group type to display suffix for "Corp <TICKER> [Suffix]"
CORPORATION_GROUP_SUFFIXES = {
    EveCorporationGroup.GROUP_TYPE_MEMBER: "",
    EveCorporationGroup.GROUP_TYPE_RECRUITER: " Recruiter",
    EveCorporationGroup.GROUP_TYPE_DIRECTOR: " Director",
    EveCorporationGroup.GROUP_TYPE_GUNNER: " Gunner",
}


def ensure_corporation_groups_for_corp(
    corporation: EveCorporation,
) -> list[EveCorporationGroup]:
    """
    For a corporation with generate_corporation_groups=True, ensure the four
    Corp <TICKER> groups exist (member, recruiter, director, gunner).
    Creates Django auth groups and EveCorporationGroup rows as needed.
    Returns the list of EveCorporationGroup for this corporation.
    """
    if not corporation.generate_corporation_groups or not corporation.ticker:
        return list(
            EveCorporationGroup.objects.filter(
                corporation=corporation
            ).order_by("group_type")
        )

    base_name = f"Corp {corporation.ticker}"
    created_groups = []

    for group_type, suffix in CORPORATION_GROUP_SUFFIXES.items():
        name = f"{base_name}{suffix}".strip()
        ecg = EveCorporationGroup.objects.filter(
            corporation=corporation, group_type=group_type
        ).first()
        if ecg:
            if ecg.group.name != name:
                ecg.group.name = name
                ecg.group.save(update_fields=["name"])
            continue
        auth_group, _ = AuthGroup.objects.get_or_create(
            name=name, defaults={"name": name}
        )
        ecg = EveCorporationGroup.objects.create(
            group=auth_group,
            corporation=corporation,
            group_type=group_type,
        )
        created_groups.append(ecg)

    return list(
        EveCorporationGroup.objects.filter(corporation=corporation).order_by(
            "group_type"
        )
    )


def offboard_corporation_groups(corporation: EveCorporation) -> None:
    """
    Offboard all corporation groups for this corporation (disconnect signal,
    then delete each auth group so Discord roles are not touched during M2M clear).
    """
    group_ids = list(
        EveCorporationGroup.objects.filter(
            corporation=corporation
        ).values_list("group_id", flat=True)
    )
    for group_id in group_ids:
        offboard_group(group_id)


def user_in_team(user: User, team_name: str) -> bool:
    team = Team.objects.filter(name=team_name).first()

    if not team:
        raise ValueError(f"Unknown team: {team_name}")

    return team.members.contains(user)
