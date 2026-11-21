"""Who may see an undisclosed campaign, and what everyone else gets.

An undisclosed campaign is for its managers and the coordinators they
invite. Everyone else sees an Upcoming Campaign with its start time and an
Enlist button: no name, no slug, no sides, no end date. The redaction is
done here, in the API, so nothing the page leaves out is still in the JSON.

A campaign is reached by its slug or by its ``public_key``. While it is
undisclosed, the slug only resolves for people who may see it, since the
slug is made from the name.
"""

from __future__ import annotations

from django.db.models import Q
from django.http import Http404

from campaigns.models import Campaign

GENERIC_NAME = "Upcoming Campaign"

MANAGER = "manager"
COORDINATOR = "coordinator"
MEMBER = "member"


def _user(user):
    return user if getattr(user, "is_authenticated", False) else None


def coordinated_ids(user) -> set[int]:
    """Campaign ids the user coordinates through any of their characters."""
    user = _user(user)
    if user is None:
        return set()
    # Imported here: eveonline imports campaigns models at load time.
    from eveonline.models import EveCharacter  # pylint: disable=C0415
    from campaigns.models import CampaignCoordinator  # pylint: disable=C0415

    character_ids = EveCharacter.objects.filter(user=user).values_list(
        "character_id", flat=True
    )
    return set(
        CampaignCoordinator.objects.filter(
            character_id__in=list(character_ids)
        ).values_list("campaign_id", flat=True)
    )


def is_manager(user, campaign: Campaign) -> bool:
    user = _user(user)
    if user is None:
        return False
    # The manage module imports the public endpoints; keep it lazy.
    from campaigns.endpoints.manage import (  # pylint: disable=C0415
        _can_manage,
    )

    return _can_manage(user, campaign)


def role(user, campaign: Campaign) -> str:
    if is_manager(user, campaign):
        return MANAGER
    if campaign.id in coordinated_ids(user):
        return COORDINATOR
    return MEMBER


def sees_details(user, campaign: Campaign) -> bool:
    if not campaign.undisclosed:
        return True
    return role(user, campaign) != MEMBER


def address(campaign: Campaign, user) -> str:
    """The path segment this viewer uses for the campaign."""
    if sees_details(user, campaign):
        return campaign.slug
    return campaign.public_key


def display_name(campaign: Campaign, user) -> str:
    if sees_details(user, campaign):
        return campaign.name
    return GENERIC_NAME


def coordinator_may(campaign: Campaign, scope: str) -> bool:
    return scope in (campaign.coordinator_scopes or [])


def resolve(queryset, key: str, user) -> Campaign:
    """The campaign at ``key`` (slug or public key) for this viewer, or 404.

    The slug of an undisclosed campaign does not resolve for people who may
    not see it, so trying names in the URL tells them nothing.
    """
    campaign = queryset.filter(Q(slug=key) | Q(public_key=key)).first()
    if campaign is None:
        raise Http404
    if (
        campaign.undisclosed
        and key != campaign.public_key
        and not sees_details(user, campaign)
    ):
        raise Http404
    return campaign
