"""
Live Discord ↔ Django fail-closed verification (test guild only).

Not run by default. Invoked via:

  pipenv run python manage.py verify_discord_groups --username <user>

or (opt-in TestCase, real settings DB — not settings_test):

  RUN_DISCORD_LIVE_VERIFY=1 pipenv run python manage.py test \\
    discord.test_live_discord_groups_verify --settings=app.settings

See docs/auth/discord-groups-verification.md.
"""

from __future__ import annotations

import logging
import os
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import signals

import discord.client as discord_client_mod
import discord.helpers as discord_helpers
import discord.signals as discord_signals
import discord.tasks as discord_tasks
from discord.client import DiscordClient
from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordRole, DiscordUser
from discord.signals import discord_user_deleting
from discord.sync_context import disable_discord_group_sync
from discord.tasks import sync_discord_user
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation
from groups.helpers import sync_user_community_groups
from groups.models import (
    AffiliationType,
    EveCorporationGroup,
    UserAffiliation,
    UserCommunityStatus,
)
from groups.tasks import sync_community_groups, sync_eve_corporation_groups
from tribes.helpers.tribe_auth_groups import (
    remove_tribe_auth_groups_for_inactive_membership,
)
from tribes.models import Tribe, TribeGroup, TribeGroupMembership
from users.helpers import offboard_user

logger = logging.getLogger(__name__)

# Hard refuse — never run live verify against production Minmatar Fleet.
PRODUCTION_DISCORD_GUILD_IDS = frozenset(
    {
        1041384161505722368,
    }
)

# Default allowlist for live OPSEC verification.
ALLOWED_LIVE_VERIFY_GUILD_IDS = frozenset(
    {
        1459994254427291781,  # Minmatar Fleet Test Server
    }
)

VERIFY_PREFIX = "VERIFY-"
ENV_ENABLE = "RUN_DISCORD_LIVE_VERIFY"


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    notes: str = ""


@dataclass
class LiveVerifyReport:
    guild_id: str
    subject: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    @property
    def ok(self) -> bool:
        return not self.failed


class LiveVerifyError(RuntimeError):
    """Safety gate or unrecoverable setup failure."""


def assert_live_verify_allowed(
    *,
    require_env: bool = False,
    allow_extra_guild_ids: frozenset[int] | None = None,
    guild_id: int | None = None,
) -> str:
    """
    Raise LiveVerifyError unless it is safe to hit live Discord.

    Production guild IDs are always refused. Guild must be in the allowlist
    (or an explicit extra allow set passed by the operator).
    """
    if require_env and os.environ.get(ENV_ENABLE) != "1":
        raise LiveVerifyError(
            f"Refusing live Discord verify: set {ENV_ENABLE}=1 to enable"
        )

    resolved = int(
        guild_id if guild_id is not None else settings.DISCORD_GUILD_ID
    )
    if resolved in PRODUCTION_DISCORD_GUILD_IDS:
        raise LiveVerifyError(
            f"Refusing live Discord verify against production guild "
            f"{resolved}. Point DISCORD_GUILD_ID at the test server "
            f"or pass --guild-id <test-guild-id>."
        )

    allowed = set(ALLOWED_LIVE_VERIFY_GUILD_IDS)
    if allow_extra_guild_ids:
        allowed |= {int(x) for x in allow_extra_guild_ids}
    if resolved not in allowed:
        raise LiveVerifyError(
            f"Refusing live Discord verify: guild {resolved} is not in the "
            f"allowlist {sorted(allowed)}. Add it only for a known test guild."
        )

    if not settings.DISCORD_BOT_TOKEN:
        raise LiveVerifyError("DISCORD_BOT_TOKEN is empty")

    return str(resolved)


def patch_discord_clients_to_guild(guild_id: str) -> None:
    """Module-level DiscordClient instances capture GUILD_ID at import time."""
    discord_client_mod.GUILD_ID = guild_id
    for client in (
        discord_signals.discord,
        discord_helpers.discord,
        discord_tasks.discord,
    ):
        client.guild_id = guild_id


@contextmanager
def broken_bot_token():
    clients = [discord_signals.discord, discord_helpers.discord]
    originals = [c.access_token for c in clients]
    for client in clients:
        client.access_token = "invalid-token-live-verify"
    try:
        yield
    finally:
        for client, token in zip(clients, originals):
            client.access_token = token


@dataclass
class LiveVerifyRunner:
    """Execute the A–H matrix against a linked Discord subject on the test guild."""

    username: str
    guild_id: str
    burst_count: int = 20
    results: list[CaseResult] = field(default_factory=list)
    created_group_names: set[str] = field(default_factory=set)
    scratch_user_ids: set[int] = field(default_factory=set)
    corp_group_id: int | None = None
    tribe_group_id: int | None = None
    verify_aff_type_id: int | None = None
    managed_role_id: str | None = None
    original_affiliation_id: int | None = None
    original_ucs: str | None = None
    original_corp_id: int | None = None

    def client(self) -> DiscordClient:
        client = DiscordClient()
        client.guild_id = self.guild_id
        return client

    def subject(self) -> User:
        return User.objects.get(username=self.username)

    def discord_id(self) -> int:
        return DiscordUser.objects.get(user=self.subject()).id

    def django_groups(self, user: User) -> set[str]:
        return set(user.groups.values_list("name", flat=True))

    def live_role_ids(self, discord_id: int) -> set[str]:
        return set(self.client().get_user(discord_id)["roles"])

    def role_id(self, group_name: str) -> str:
        return str(DiscordRole.objects.get(group__name=group_name).role_id)

    def members_linked(self, group_name: str, user: User) -> bool:
        return (
            DiscordRole.objects.get(group__name=group_name)
            .members.filter(user=user)
            .exists()
        )

    def ensure_group(self, name: str) -> Group:
        if not name.startswith(VERIFY_PREFIX):
            raise LiveVerifyError(
                f"Scratch groups must use {VERIFY_PREFIX}: {name}"
            )
        group, _ = Group.objects.get_or_create(name=name)
        self.created_group_names.add(name)
        return group

    def point_role_at_managed(self, group_name: str) -> str:
        role = DiscordRole.objects.get(group__name=group_name)
        previous = str(role.role_id)
        role.role_id = int(self.managed_role_id)
        role.save(update_fields=["role_id", "updated_at"])
        return previous

    def restore_role_id(self, group_name: str, role_id: str) -> None:
        role = DiscordRole.objects.get(group__name=group_name)
        role.role_id = int(role_id)
        role.save(update_fields=["role_id", "updated_at"])

    def record(self, case_id: str, passed: bool, notes: str = "") -> None:
        self.results.append(CaseResult(case_id, passed, notes))
        logger.info(
            "LIVE_VERIFY %s %s %s",
            case_id,
            "PASS" if passed else "FAIL",
            notes,
        )

    def run_case(self, case_id: str, fn: Callable[[], str | None]) -> None:
        try:
            notes = fn() or ""
            self.record(case_id, True, notes)
        except Exception as exc:  # noqa: BLE001 — collect per-case failures
            self.record(
                case_id,
                False,
                f"{exc}\n{traceback.format_exc()}",
            )

    def discover_managed_role_id(self) -> str:
        for role in self.client().get_roles():
            if role.get("managed") and str(role["id"]) != self.guild_id:
                return str(role["id"])
        raise LiveVerifyError(
            "No managed Discord role found to induce 403 Missing Permissions"
        )

    def setup(self) -> None:
        user = self.subject()
        if not DiscordUser.objects.filter(user=user).exists():
            raise LiveVerifyError(
                f"Subject {self.username} has no DiscordUser (must be guild-linked)"
            )

        self.managed_role_id = self.discover_managed_role_id()

        ua = UserAffiliation.objects.filter(user=user).first()
        self.original_affiliation_id = ua.affiliation_id if ua else None
        try:
            self.original_ucs = user.community_status.status
        except UserCommunityStatus.DoesNotExist:
            self.original_ucs = UserCommunityStatus.STATUS_ACTIVE
        primary = user_primary_character(user)
        self.original_corp_id = primary.corporation_id if primary else None

        no_discord, _ = User.objects.get_or_create(
            username="verify-no-discord"
        )
        DiscordUser.objects.filter(user=no_discord).delete()
        self.scratch_user_ids.add(no_discord.id)

        for name in ("Alliance", "Guest", "On Leave", "Trial"):
            group = Group.objects.get(name=name)
            if not DiscordRole.objects.filter(group=group).exists():
                DiscordRole.objects.create(name=name, group=group)

        aff_group = self.ensure_group("VERIFY-Aff")
        aff, _ = AffiliationType.objects.get_or_create(
            name="VERIFY-Aff",
            defaults={
                "group": aff_group,
                "priority": 2,
                "requires_trial": False,
            },
        )
        if aff.group_id != aff_group.id:
            aff.group = aff_group
            aff.save(update_fields=["group"])
        self.verify_aff_type_id = aff.id

        tribe = (
            Tribe.objects.filter(name="Capitals").first()
            or Tribe.objects.filter(is_active=True).first()
        )
        if tribe is None:
            raise LiveVerifyError("No Tribe available for VERIFY tribe group")
        tg_auth = self.ensure_group("VERIFY-TribeGroup")
        tribe_group, _ = TribeGroup.objects.get_or_create(
            code="verify.live",
            defaults={
                "tribe": tribe,
                "name": "VERIFY Live",
                "group": tg_auth,
                "is_active": True,
            },
        )
        if tribe_group.group_id != tg_auth.id:
            tribe_group.group = tg_auth
            tribe_group.save(update_fields=["group"])
        self.tribe_group_id = tribe_group.id

        if self.original_corp_id is None:
            raise LiveVerifyError(
                f"Subject {self.username} needs a primary character with corporation_id"
            )
        corp = EveCorporation.objects.get(corporation_id=self.original_corp_id)
        corp_auth = self.ensure_group("VERIFY-Corp-Member")
        ecg, _ = EveCorporationGroup.objects.get_or_create(
            corporation=corp,
            group_type=EveCorporationGroup.GROUP_TYPE_MEMBER,
            defaults={"group": corp_auth},
        )
        if ecg.group_id != corp_auth.id:
            ecg.group = corp_auth
            ecg.save(update_fields=["group"])
        self.corp_group_id = ecg.id

    def restore_subject(self) -> None:
        user = self.subject()
        if self.original_affiliation_id:
            affiliation = AffiliationType.objects.get(
                pk=self.original_affiliation_id
            )
            ua = UserAffiliation.objects.filter(user=user).first()
            if ua is None:
                UserAffiliation.objects.create(
                    user=user, affiliation=affiliation
                )
            elif ua.affiliation_id != affiliation.id:
                ua.affiliation = affiliation
                ua.save()
        ucs, _ = UserCommunityStatus.objects.get_or_create(
            user=user,
            defaults={
                "status": self.original_ucs
                or UserCommunityStatus.STATUS_ACTIVE
            },
        )
        desired = self.original_ucs or UserCommunityStatus.STATUS_ACTIVE
        if ucs.status != desired:
            ucs.status = desired
            ucs.save()
        primary = user_primary_character(user)
        if (
            primary is not None
            and self.original_corp_id is not None
            and primary.corporation_id != self.original_corp_id
        ):
            primary.corporation_id = self.original_corp_id
            primary.save(update_fields=["corporation_id", "updated_at"])
        sync_user_community_groups(user)
        sync_discord_user(user.id)

    def _cleanup_scratch_sources(self) -> None:
        if self.corp_group_id:
            EveCorporationGroup.objects.filter(id=self.corp_group_id).delete()
        if self.tribe_group_id:
            TribeGroupMembership.objects.filter(
                tribe_group_id=self.tribe_group_id
            ).delete()
            TribeGroup.objects.filter(id=self.tribe_group_id).delete()
        if self.verify_aff_type_id:
            AffiliationType.objects.filter(id=self.verify_aff_type_id).delete()
        AffiliationType.objects.filter(name="VERIFY-B4-Aff").delete()

    def _cleanup_scratch_users(self) -> None:
        signals.pre_delete.disconnect(
            discord_user_deleting,
            sender=DiscordUser,
            dispatch_uid="discord_user_deleting",
        )
        try:
            for user_id in list(self.scratch_user_ids):
                User.objects.filter(id=user_id).delete()
            for username in (
                "verify-no-discord",
                "verify-b",
                "verify-g1-offboard",
                "verify-d2-orphan",
                "verify-f3-offboard",
            ):
                User.objects.filter(username=username).delete()
        finally:
            signals.pre_delete.connect(
                discord_user_deleting,
                sender=DiscordUser,
                dispatch_uid="discord_user_deleting",
            )

    def _cleanup_verify_roles_and_groups(self) -> None:
        client = self.client()
        for name in list(self.created_group_names):
            role = DiscordRole.objects.filter(group__name=name).first()
            if role and role.role_id:
                try:
                    client.delete_role(role.role_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cleanup discord role %s: %s", name, exc)
            Group.objects.filter(name=name).delete()

    def cleanup(self) -> None:
        user = self.subject()
        for name in list(self.created_group_names):
            group = Group.objects.filter(name=name).first()
            if group and user.groups.filter(pk=group.pk).exists():
                try:
                    user.groups.remove(group)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cleanup remove %s: %s", name, exc)

        self._cleanup_scratch_sources()
        self._cleanup_scratch_users()
        self._cleanup_verify_roles_and_groups()
        self.restore_subject()

    # ---- cases ----

    def case_a1(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-Role")
        user.groups.add(group)
        assert "VERIFY-Role" in self.django_groups(user)
        assert self.role_id("VERIFY-Role") in self.live_role_ids(
            self.discord_id()
        )
        assert self.members_linked("VERIFY-Role", user)
        return "add aligned"

    def case_a2(self) -> str:
        user = self.subject()
        group = Group.objects.get(name="VERIFY-Role")
        user.groups.remove(group)
        assert "VERIFY-Role" not in self.django_groups(user)
        assert self.role_id("VERIFY-Role") not in self.live_role_ids(
            self.discord_id()
        )
        return "remove aligned"

    def case_a3(self) -> str:
        group = self.ensure_group("VERIFY-New")
        role = DiscordRole.objects.get(group=group)
        assert role.role_id
        names = {r["name"]: r["id"] for r in self.client().get_roles()}
        assert names.get("VERIFY-New") == str(role.role_id)
        return f"role_id={role.role_id}"

    def case_a4(self) -> str:
        user = self.subject()
        sync_user_community_groups(user)
        sync_discord_user(user.id)
        live = self.live_role_ids(self.discord_id())
        assert "Alliance" in self.django_groups(user)
        assert self.role_id("Alliance") in live
        assert "On Leave" not in self.django_groups(user)
        assert self.role_id("On Leave") not in live
        return "Alliance on Discord+Django; On Leave cleared"

    def case_a5(self) -> str:
        user = self.subject()
        tribe_group = TribeGroup.objects.get(id=self.tribe_group_id)
        membership, _ = TribeGroupMembership.objects.get_or_create(
            user=user,
            tribe_group=tribe_group,
            defaults={"status": TribeGroupMembership.STATUS_PENDING},
        )
        membership.status = TribeGroupMembership.STATUS_ACTIVE
        membership.save()
        assert "VERIFY-TribeGroup" in self.django_groups(user)
        assert self.role_id("VERIFY-TribeGroup") in self.live_role_ids(
            self.discord_id()
        )
        return "tribe group active aligned"

    def case_a6(self) -> str:
        user = self.subject()
        sync_eve_corporation_groups()
        assert "VERIFY-Corp-Member" in self.django_groups(user)
        assert self.role_id("VERIFY-Corp-Member") in self.live_role_ids(
            self.discord_id()
        )
        return "corp member sync aligned"

    def case_b1(self) -> str:
        group = self.ensure_group("VERIFY-Role")
        no_discord = User.objects.get(username="verify-no-discord")
        try:
            no_discord.groups.add(group)
            raise AssertionError("expected DiscordRoleAssignmentError")
        except DiscordRoleAssignmentError:
            pass
        assert "VERIFY-Role" not in self.django_groups(no_discord)
        return "no DiscordUser blocked"

    def case_b2(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-B2")
        previous = self.point_role_at_managed("VERIFY-B2")
        try:
            try:
                with transaction.atomic():
                    user.groups.add(group)
                raise AssertionError("expected DiscordRoleAssignmentError")
            except DiscordRoleAssignmentError:
                pass
            assert "VERIFY-B2" not in self.django_groups(user)
            return "403 add blocked; not in Django"
        finally:
            self.restore_role_id("VERIFY-B2", previous)

    def case_b3(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-B3")
        with broken_bot_token():
            try:
                with transaction.atomic():
                    user.groups.add(group)
                raise AssertionError("expected DiscordRoleAssignmentError")
            except DiscordRoleAssignmentError:
                pass
        assert "VERIFY-B3" not in self.django_groups(user)
        return "bad token blocked add"

    def case_b4(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-B4-Aff")
        aff, _ = AffiliationType.objects.get_or_create(
            name="VERIFY-B4-Aff",
            defaults={"group": group, "priority": 3, "requires_trial": False},
        )
        self.created_group_names.add("VERIFY-B4-Aff")
        previous = self.point_role_at_managed("VERIFY-B4-Aff")
        alliance = AffiliationType.objects.get(name="Alliance")
        ua = UserAffiliation.objects.get(user=user)
        try:
            try:
                ua.affiliation = aff
                ua.save()
                raise AssertionError("expected affiliation rollback")
            except DiscordRoleAssignmentError:
                pass
            ua.refresh_from_db()
            assert ua.affiliation_id == alliance.id
            assert "VERIFY-B4-Aff" not in self.django_groups(user)
            return "affiliation rolled back on Discord fail"
        finally:
            self.restore_role_id("VERIFY-B4-Aff", previous)
            AffiliationType.objects.filter(name="VERIFY-B4-Aff").delete()
            ua.refresh_from_db()
            if ua.affiliation_id != alliance.id:
                ua.affiliation = alliance
                ua.save()

    def case_c1(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-C1")
        user.groups.add(group)
        previous = self.point_role_at_managed("VERIFY-C1")
        try:
            try:
                with transaction.atomic():
                    user.groups.remove(group)
                raise AssertionError("expected DiscordRoleAssignmentError")
            except DiscordRoleAssignmentError:
                pass
            assert "VERIFY-C1" in self.django_groups(user)
            assert previous in self.live_role_ids(self.discord_id())
            return "403 remove kept Django+Discord"
        finally:
            self.restore_role_id("VERIFY-C1", previous)
            if "VERIFY-C1" in self.django_groups(user):
                user.groups.remove(group)

    def case_c2(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-C2")
        user.groups.add(group)
        with broken_bot_token():
            try:
                with transaction.atomic():
                    user.groups.remove(group)
                raise AssertionError("expected DiscordRoleAssignmentError")
            except DiscordRoleAssignmentError:
                pass
        assert "VERIFY-C2" in self.django_groups(user)
        assert self.role_id("VERIFY-C2") in self.live_role_ids(
            self.discord_id()
        )
        user.groups.remove(group)
        return "unreachable remove kept both"

    def case_c3(self) -> str:
        user = self.subject()
        tribe_group = TribeGroup.objects.get(id=self.tribe_group_id)
        membership = TribeGroupMembership.objects.get(
            user=user, tribe_group=tribe_group
        )
        if membership.status != TribeGroupMembership.STATUS_ACTIVE:
            membership.status = TribeGroupMembership.STATUS_ACTIVE
            membership.save()
        previous = self.point_role_at_managed("VERIFY-TribeGroup")
        try:
            try:
                membership.status = TribeGroupMembership.STATUS_INACTIVE
                membership.save()
                raise AssertionError("expected inactive rollback")
            except DiscordRoleAssignmentError:
                pass
            membership.refresh_from_db()
            assert membership.status == TribeGroupMembership.STATUS_ACTIVE
            assert "VERIFY-TribeGroup" in self.django_groups(user)
            assert previous in self.live_role_ids(self.discord_id())
            return "tribe inactive rolled back; roles kept"
        finally:
            self.restore_role_id("VERIFY-TribeGroup", previous)

    def case_c4(self) -> str:
        user = self.subject()
        previous = self.point_role_at_managed("Alliance")
        guest = AffiliationType.objects.get(name="Guest")
        ua = UserAffiliation.objects.get(user=user)
        try:
            try:
                ua.affiliation = guest
                ua.save()
                raise AssertionError("expected demotion failure/rollback")
            except DiscordRoleAssignmentError:
                pass
            ua.refresh_from_db()
            django_names = self.django_groups(user)
            live = self.live_role_ids(self.discord_id())
            if "Guest" in django_names and "Alliance" not in django_names:
                if previous in live:
                    raise AssertionError(
                        "OPSEC: Guest in Django but Alliance still on Discord"
                    )
            assert (
                ua.affiliation.name == "Alliance" or "Alliance" in django_names
            )
            return f"demotion blocked; aff={ua.affiliation.name}"
        finally:
            self.restore_role_id("Alliance", previous)
            self.restore_subject()

    def case_c5(self) -> str:
        user = self.subject()
        group = self.ensure_group("VERIFY-C5")
        user.groups.add(group)
        user.groups.remove(group)
        assert "VERIFY-C5" not in self.django_groups(user)
        assert self.role_id("VERIFY-C5") not in self.live_role_ids(
            self.discord_id()
        )
        sync_user_community_groups(user)
        return "converge after restore OK"

    def case_d1(self) -> str:
        g1, _ = User.objects.get_or_create(username="verify-g1-offboard")
        self.scratch_user_ids.add(g1.id)
        DiscordUser.objects.filter(user=g1).delete()
        fake_id = 199999999999999999
        DiscordUser.objects.filter(id=fake_id).delete()
        DiscordUser.objects.create(
            id=fake_id, user=g1, discord_tag="verify-g1#0"
        )
        group = self.ensure_group("VERIFY-D1")
        with disable_discord_group_sync():
            g1.groups.add(group)
        try:
            g1.groups.remove(group)
        except User.DoesNotExist:
            return "10007 remove allowed; user offboarded during handle"
        if not User.objects.filter(username="verify-g1-offboard").exists():
            return "10007 remove allowed; user offboarded"
        assert "VERIFY-D1" not in self.django_groups(g1)
        return "10007 remove allowed; user still present"

    def case_d2(self) -> str:
        tmp, _ = User.objects.get_or_create(username="verify-d2-orphan")
        self.scratch_user_ids.add(tmp.id)
        group = self.ensure_group("VERIFY-D2")
        with disable_discord_group_sync():
            tmp.groups.add(group)
        DiscordUser.objects.filter(user=tmp).delete()
        tmp.groups.remove(group)
        assert "VERIFY-D2" not in self.django_groups(tmp)
        return "no DiscordUser remove allowed"

    def case_e1(self) -> str:
        user = self.subject()
        guest = AffiliationType.objects.get(name="Guest")
        UserAffiliation.objects.filter(user=user).update(affiliation=guest)
        alliance_group = Group.objects.get(name="Alliance")
        if "Alliance" not in self.django_groups(user):
            user.groups.add(alliance_group)
        sync_user_community_groups(user)
        live = self.live_role_ids(self.discord_id())
        django_names = self.django_groups(user)
        assert "Alliance" not in django_names
        assert "Guest" in django_names
        assert self.role_id("Alliance") not in live
        assert self.role_id("Guest") in live
        self.restore_subject()
        return "stale Alliance stripped; Guest only"

    def case_e2(self) -> str:
        user = self.subject()
        tribe_group = TribeGroup.objects.get(id=self.tribe_group_id)
        membership = TribeGroupMembership.objects.get(
            user=user, tribe_group=tribe_group
        )
        TribeGroupMembership.objects.filter(pk=membership.pk).update(
            status=TribeGroupMembership.STATUS_INACTIVE
        )
        membership.refresh_from_db()
        if "VERIFY-TribeGroup" not in self.django_groups(user):
            user.groups.add(Group.objects.get(name="VERIFY-TribeGroup"))
        remove_tribe_auth_groups_for_inactive_membership(membership)
        assert "VERIFY-TribeGroup" not in self.django_groups(user)
        assert self.role_id("VERIFY-TribeGroup") not in self.live_role_ids(
            self.discord_id()
        )
        return "inactive tribe groups stripped"

    def case_e3(self) -> str:
        user = self.subject()
        sync_eve_corporation_groups()
        assert "VERIFY-Corp-Member" in self.django_groups(user)
        primary = user_primary_character(user)
        old = primary.corporation_id
        primary.corporation_id = 98498664  # any other known corp
        primary.save(update_fields=["corporation_id", "updated_at"])
        try:
            sync_eve_corporation_groups()
            assert "VERIFY-Corp-Member" not in self.django_groups(user)
            assert self.role_id(
                "VERIFY-Corp-Member"
            ) not in self.live_role_ids(self.discord_id())
            return "corp role removed after primary change"
        finally:
            primary.corporation_id = old
            primary.save(update_fields=["corporation_id", "updated_at"])

    def case_f1(self) -> str:
        user = self.subject()
        groups = []
        for index in range(self.burst_count):
            group = self.ensure_group(f"VERIFY-Burst-{index}")
            groups.append(group)
            user.groups.add(group)
        live = self.live_role_ids(self.discord_id())
        django_names = self.django_groups(user)
        for group in groups:
            assert group.name in django_names
            assert self.role_id(group.name) in live
        return f"{self.burst_count} burst-adds aligned"

    def case_f2(self) -> str:
        user = self.subject()
        groups = [
            Group.objects.get(name=f"VERIFY-Burst-{index}")
            for index in range(self.burst_count)
        ]
        for group in groups:
            if group.name in self.django_groups(user):
                user.groups.remove(group)
        live = self.live_role_ids(self.discord_id())
        for group in groups:
            assert group.name not in self.django_groups(user)
            assert self.role_id(group.name) not in live
        return f"{self.burst_count} burst-removes aligned"

    def case_f3(self) -> str:
        user = self.subject()
        tmp, _ = User.objects.get_or_create(username="verify-f3-offboard")
        self.scratch_user_ids.add(tmp.id)
        DiscordUser.objects.filter(user=tmp).delete()
        DiscordUser.objects.create(
            id=188888888888888888, user=tmp, discord_tag="verify-f3#0"
        )
        offboard_user(tmp.id)
        group = self.ensure_group("VERIFY-F3")
        user.groups.add(group)
        assert self.role_id("VERIFY-F3") in self.live_role_ids(
            self.discord_id()
        )
        user.groups.remove(group)
        sync_community_groups()
        return "post-offboard sync still works for subject"

    def case_g1(self) -> str:
        g1, _ = User.objects.get_or_create(username="verify-g1-offboard")
        self.scratch_user_ids.add(g1.id)
        DiscordUser.objects.filter(user=g1).delete()
        DiscordUser.objects.filter(id=177777777777777777).delete()
        DiscordUser.objects.create(
            id=177777777777777777, user=g1, discord_tag="verify-g1#0"
        )
        group = self.ensure_group("VERIFY-G1")
        with disable_discord_group_sync():
            g1.groups.add(group)
        user_id = g1.id
        offboard_user(user_id)
        assert not User.objects.filter(id=user_id).exists()
        return "throwaway offboarded (never the subject)"

    def case_g2(self) -> str:
        """G2: sync still works after G1 — uses subject (not a second human)."""
        user = self.subject()
        group = self.ensure_group("VERIFY-G2")
        user.groups.add(group)
        assert self.role_id("VERIFY-G2") in self.live_role_ids(
            self.discord_id()
        )
        user.groups.remove(group)
        return "subject still syncs after throwaway offboard"

    def case_h1(self) -> str:
        user = self.subject()
        self.restore_subject()
        ucs = UserCommunityStatus.objects.get(user=user)
        ucs.status = UserCommunityStatus.STATUS_ON_LEAVE
        ucs.save()
        django_names = self.django_groups(user)
        live = self.live_role_ids(self.discord_id())
        assert "On Leave" in django_names
        assert "Alliance" not in django_names
        assert self.role_id("On Leave") in live
        assert self.role_id("Alliance") not in live
        return "On Leave only"

    def case_h2(self) -> str:
        user = self.subject()
        guest = AffiliationType.objects.get(name="Guest")
        ua = UserAffiliation.objects.get(user=user)
        ua.affiliation = guest
        ua.save()
        ucs = UserCommunityStatus.objects.get(user=user)
        ucs.status = UserCommunityStatus.STATUS_ACTIVE
        ucs.save()
        django_names = self.django_groups(user)
        live = self.live_role_ids(self.discord_id())
        assert "Guest" in django_names
        assert "On Leave" not in django_names
        assert "Alliance" not in django_names
        assert self.role_id("Guest") in live
        assert self.role_id("On Leave") not in live
        return "Guest only"

    def case_h3(self) -> str:
        user = self.subject()
        self.restore_subject()
        previous = self.point_role_at_managed("Alliance")
        ucs = UserCommunityStatus.objects.get(user=user)
        try:
            try:
                ucs.status = UserCommunityStatus.STATUS_ON_LEAVE
                ucs.save()
            except DiscordRoleAssignmentError:
                pass
            django_names = self.django_groups(user)
            self.restore_role_id("Alliance", previous)
            live = self.live_role_ids(self.discord_id())
            if (
                "On Leave" in django_names
                and "Alliance" not in django_names
                and previous in live
            ):
                raise AssertionError(
                    "OPSEC: On Leave Django + Alliance still on Discord"
                )
            return (
                "interrupted leave handled; "
                f"community={sorted(n for n in django_names if n in ('Alliance', 'On Leave', 'Guest', 'Trial'))}"
            )
        finally:
            try:
                self.restore_role_id("Alliance", previous)
            except Exception:  # noqa: BLE001
                pass
            self.restore_subject()

    def run(self, case_ids: set[str] | None = None) -> LiveVerifyReport:
        patch_discord_clients_to_guild(self.guild_id)
        self.setup()

        all_cases: list[tuple[str, Callable[[], str | None]]] = [
            ("A1", self.case_a1),
            ("A2", self.case_a2),
            ("A3", self.case_a3),
            ("A4", self.case_a4),
            ("A5", self.case_a5),
            ("A6", self.case_a6),
            ("B1", self.case_b1),
            ("B2", self.case_b2),
            ("B3", self.case_b3),
            ("B4", self.case_b4),
            ("C1", self.case_c1),
            ("C2", self.case_c2),
            ("C3", self.case_c3),
            ("C4", self.case_c4),
            ("C5", self.case_c5),
            ("D1", self.case_d1),
            ("D2", self.case_d2),
            ("E1", self.case_e1),
            ("E2", self.case_e2),
            ("E3", self.case_e3),
            ("F1", self.case_f1),
            ("F2", self.case_f2),
            ("F3", self.case_f3),
            ("G1", self.case_g1),
            ("G2", self.case_g2),
            ("H1", self.case_h1),
            ("H2", self.case_h2),
            ("H3", self.case_h3),
        ]

        try:
            for case_id, fn in all_cases:
                if case_ids is not None and case_id not in case_ids:
                    continue
                self.run_case(case_id, fn)
        finally:
            try:
                self.cleanup()
            except Exception:  # noqa: BLE001
                logger.exception("LIVE_VERIFY cleanup failed")

        return LiveVerifyReport(
            guild_id=self.guild_id,
            subject=self.username,
            results=list(self.results),
        )


def run_live_discord_groups_verify(
    *,
    username: str,
    require_env: bool = False,
    allow_extra_guild_ids: frozenset[int] | None = None,
    case_ids: set[str] | None = None,
    burst_count: int = 20,
    guild_id: int | None = None,
) -> LiveVerifyReport:
    resolved = assert_live_verify_allowed(
        require_env=require_env,
        allow_extra_guild_ids=allow_extra_guild_ids,
        guild_id=guild_id,
    )
    runner = LiveVerifyRunner(
        username=username,
        guild_id=resolved,
        burst_count=burst_count,
    )
    return runner.run(case_ids=case_ids)
