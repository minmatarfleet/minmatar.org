"""Create, rename and archive tribes and tribe groups from the site.

Owned by the ``tribes.structure.manage`` feature (People Team by default).
The Django admin stays as break-glass for superusers.

Creating a tribe or group also creates its linked auth group, named after
it; the ``group_post_save`` signal in ``discord.signals`` then makes (or
links) the Discord role. Renaming renames the auth group and the Discord
role with it. Slugs and group codes never change: reports and bindings key
on them.
"""

from __future__ import annotations

import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.utils.text import slugify

from audit.helpers import record_audit
from discord.client import DiscordClient
from discord.models import DiscordRole
from groups.helpers.feature_access import can_use_feature, user_has_legacy_perm
from tribes.models import Tribe, TribeGroup

logger = logging.getLogger(__name__)

FEATURE = "tribes.structure.manage"
LEGACY_PERMISSION = "tribes.change_tribe"
NAME_MAX = 128
DESCRIPTION_MAX = 2000


class StructureError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def can_manage_structure(user) -> bool:
    """The feature, or the admin's change-tribe permission (superusers
    always)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return can_use_feature(user, FEATURE) or user_has_legacy_perm(
        user, LEGACY_PERMISSION
    )


def _require(by) -> None:
    if not can_manage_structure(by):
        raise StructureError(
            "You can't create or change tribes.", status_code=403
        )


def _clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise StructureError("Give it a name.")
    if len(name) > NAME_MAX:
        raise StructureError(f"Keep the name under {NAME_MAX} characters.")
    return name


def _clean_description(description: str) -> str:
    description = (description or "").strip()
    if len(description) > DESCRIPTION_MAX:
        raise StructureError(
            f"Keep the description under {DESCRIPTION_MAX} characters."
        )
    return description


def _free_auth_group_name(name: str, current: Group | None = None) -> None:
    taken = Group.objects.filter(name=name)
    if current is not None:
        taken = taken.exclude(pk=current.pk)
    if taken.exists():
        raise StructureError(
            f"A group or Discord role called {name} already exists. "
            "Pick another name."
        )


def _new_auth_group(name: str) -> Group:
    """The linked auth group; its Discord role comes from the signal."""
    _free_auth_group_name(name)
    return Group.objects.create(name=name)


def _rename_auth_group(group: Group | None, name: str) -> None:
    """Rename the linked auth group and its Discord role.

    Runs inside the caller's transaction: a Discord failure raises and
    nothing is renamed.
    """
    if group is None or group.name == name:
        return
    _free_auth_group_name(name, current=group)
    group.name = name
    group.save(update_fields=["name"])
    role = DiscordRole.objects.filter(group=group).first()
    if role is None:
        return
    if role.role_id:
        DiscordClient().edit_role(role.role_id, name)
    role.name = name
    role.save(update_fields=["name", "updated_at"])


def create_tribe(by, *, name: str, slug: str = "", description: str = ""):
    _require(by)
    name = _clean_name(name)
    slug = slugify(slug or name)[:128]
    if not slug:
        raise StructureError("Give it a slug with letters or numbers.")
    if Tribe.objects.filter(slug=slug).exists():
        raise StructureError(f"A tribe already uses the slug {slug}.")
    description = _clean_description(description)
    with transaction.atomic():
        tribe = Tribe.objects.create(
            name=name,
            slug=slug,
            description=description,
            group=_new_auth_group(name),
        )
        record_audit(by, f"Created tribe {name}")
    return tribe


def create_tribe_group(by, tribe: Tribe, *, name: str, description: str = ""):
    _require(by)
    if not tribe.is_active:
        raise StructureError("Restore the tribe before adding groups.")
    name = _clean_name(name)
    if TribeGroup.objects.filter(tribe=tribe, name__iexact=name).exists():
        raise StructureError(
            f"{tribe.name} already has a group called {name}."
        )
    description = _clean_description(description)
    with transaction.atomic():
        tribe_group = TribeGroup(
            tribe=tribe,
            name=name,
            description=description,
            group=_new_auth_group(name),
        )
        tribe_group.save()
        record_audit(by, f"Created group {name} in {tribe.name}")
    return tribe_group


def _changes(obj, name: str | None, is_active: bool | None) -> list[str]:
    changes = []
    if name is not None and name != obj.name:
        changes.append(f"renamed {obj.name} to {name}")
    if is_active is not None and is_active != obj.is_active:
        changes.append("restored" if is_active else "archived")
    return changes


def update_tribe(
    by, tribe: Tribe, *, name: str | None = None, is_active: bool | None = None
) -> Tribe:
    _require(by)
    if name is not None:
        name = _clean_name(name)
    changes = _changes(tribe, name, is_active)
    if not changes:
        return tribe
    with transaction.atomic():
        tribe = Tribe.objects.select_for_update().get(pk=tribe.pk)
        if name is not None and name != tribe.name:
            _rename_auth_group(tribe.group, name)
            tribe.name = name
        if is_active is not None:
            tribe.is_active = is_active
        tribe.save(update_fields=["name", "is_active", "updated_at"])
        summary = ", ".join(changes)
        record_audit(by, f"Tribe {tribe.name}: {summary}")
    return tribe


def update_tribe_group(
    by,
    tribe_group: TribeGroup,
    *,
    name: str | None = None,
    is_active: bool | None = None,
) -> TribeGroup:
    _require(by)
    if name is not None:
        name = _clean_name(name)
        if (
            TribeGroup.objects.filter(
                tribe_id=tribe_group.tribe_id, name__iexact=name
            )
            .exclude(pk=tribe_group.pk)
            .exists()
        ):
            raise StructureError(
                f"{tribe_group.tribe.name} already has a group called {name}."
            )
    if is_active and not tribe_group.tribe.is_active:
        raise StructureError("Restore the tribe before its groups.")
    changes = _changes(tribe_group, name, is_active)
    if not changes:
        return tribe_group
    with transaction.atomic():
        tribe_group = (
            TribeGroup.objects.select_for_update()
            .select_related("tribe", "group")
            .get(pk=tribe_group.pk)
        )
        if name is not None and name != tribe_group.name:
            _rename_auth_group(tribe_group.group, name)
            tribe_group.name = name
        if is_active is not None:
            tribe_group.is_active = is_active
        tribe_group.save()
        summary = ", ".join(changes)
        record_audit(
            by,
            f"Group {tribe_group.name} in {tribe_group.tribe.name}: "
            f"{summary}",
        )
    return tribe_group
