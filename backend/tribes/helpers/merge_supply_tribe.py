"""
Merge Industry + Market tribes into Supply (catalog + auth + Discord renames).

Intended to be driven by ``manage.py merge_supply_tribe``. Prefer
``user.groups.add`` / ``.remove`` so Discord role sync signals fire.
Rename Discord roles in place via ``DiscordClient.edit_role`` (same role_id).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils import timezone

from discord.client import DiscordClient
from discord.models import DiscordRole
from industry.models import IndustryOrder
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupMembership,
    TribeGroupRank,
    TribeGroupRequirement,
)

logger = logging.getLogger(__name__)

INDUSTRY_AUTH = "Tribe - Industry"
MARKET_AUTH = "Tribe - Market"
SUPPLY_AUTH = "Tribe - Supply"
CONTRACTS_AUTH = "Tribe Group - Contracts"
ORDERS_AUTH = "Tribe Group - Market Orders"
MARKET_GROUP_AUTH = "Tribe Group - Market"

CODE_RENAMES = {
    "industry.mining": "supply.mining",
    "industry.planetary-interaction": "supply.planetary-interaction",
    "industry.capital-production": "supply.capital-production",
    "industry.subcapital-production": "supply.subcapital-production",
    "market.freighters": "supply.freighters",
    "market.loyalty-points": "supply.loyalty-points",
    "market.contracts": "supply.market",
}

SUPPLY_DESCRIPTION = (
    "Ore to hangar to market. Keeping the alliance supply chain alive — "
    "mining, industry, freight, and market."
)


@dataclass
class MergeLog:
    lines: list[str] = field(default_factory=list)

    def info(self, msg: str) -> None:
        self.lines.append(msg)
        logger.info(msg)


def _rename_auth_group(
    old_name: str,
    new_name: str,
    *,
    apply: bool,
    log: MergeLog,
    discord: DiscordClient | None,
) -> Group | None:
    """Rename Django Group (+ DiscordRole name / Discord edit_role). Idempotent."""
    existing_new = Group.objects.filter(name=new_name).first()
    old = Group.objects.filter(name=old_name).first()

    if existing_new and not old:
        log.info(f"Auth group already named {new_name!r} (skip rename)")
        return existing_new
    if existing_new and old and existing_new.pk != old.pk:
        raise RuntimeError(
            f"Both {old_name!r} and {new_name!r} exist (ids "
            f"{old.pk}, {existing_new.pk}); resolve manually."
        )
    if not old:
        if apply:
            log.info(
                f"Auth group {old_name!r} not found; creating {new_name!r}"
            )
            return Group.objects.create(name=new_name)
        log.info(
            f"Auth group {old_name!r} not found; would create {new_name!r}"
        )
        return None

    log.info(f"Rename auth group {old_name!r} → {new_name!r} (id={old.pk})")
    if not apply:
        return old

    old.name = new_name
    old.save(update_fields=["name"])

    role = DiscordRole.objects.filter(group=old).first()
    if role:
        if role.name != new_name:
            log.info(
                f"Rename DiscordRole db name {role.name!r} → {new_name!r} "
                f"(role_id={role.role_id})"
            )
            role.name = new_name
            role.save()
        if discord is not None and role.role_id:
            log.info(
                f"Discord edit_role role_id={role.role_id} name={new_name!r}"
            )
            discord.edit_role(role.role_id, new_name)
    else:
        log.info(f"No DiscordRole linked to auth group {new_name!r}")
    return old


def _move_auth_members(
    source_name: str,
    dest: Group,
    *,
    apply: bool,
    log: MergeLog,
) -> int:
    """Add each source member to dest then remove from source (Discord signals)."""
    source = Group.objects.filter(name=source_name).first()
    if not source:
        log.info(f"No auth group {source_name!r} to drain")
        return 0
    if source.pk == dest.pk:
        log.info(
            f"Source and dest are the same group {dest.name!r}; skip drain"
        )
        return 0

    users = list(source.user_set.all().order_by("id"))
    moved = 0
    for user in users:
        in_dest = user.groups.filter(pk=dest.pk).exists()
        if not in_dest:
            log.info(
                f"Auth: add {user.username} to {dest.name!r} "
                f"(from {source_name!r})"
            )
            if apply:
                user.groups.add(dest)
            moved += 1
        else:
            log.info(
                f"Auth: {user.username} already in {dest.name!r}; "
                f"remove from {source_name!r}"
            )
        if apply and user.groups.filter(pk=source.pk).exists():
            user.groups.remove(source)
        elif not apply:
            log.info(
                f"Auth: would remove {user.username} from {source_name!r}"
            )
    return moved


def _status_rank(status: str) -> int:
    order = {
        TribeGroupMembership.STATUS_ACTIVE: 3,
        TribeGroupMembership.STATUS_PENDING: 2,
        TribeGroupMembership.STATUS_INACTIVE: 1,
    }
    return order.get(status, 0)


def _merge_membership_into_survivor(
    orders_m: TribeGroupMembership,
    survivor: TribeGroup,
    *,
    apply: bool,
    log: MergeLog,
) -> None:
    """Point Orders membership at survivor, or fold into existing survivor row."""
    existing = (
        TribeGroupMembership.objects.filter(
            user_id=orders_m.user_id, tribe_group=survivor
        )
        .exclude(pk=orders_m.pk)
        .first()
    )
    if existing is None:
        log.info(
            f"Membership: move {orders_m.user.username} "
            f"{orders_m.tribe_group.code} → {survivor.code} "
            f"(status={orders_m.status})"
        )
        if apply:
            orders_m.tribe_group = survivor
            if (
                orders_m.rank_id
                and orders_m.rank.tribe_group_id != survivor.pk
            ):
                orders_m.rank = None
            orders_m.save()
        return

    # Prefer higher-value status on survivor; copy chars; retire orders row.
    if _status_rank(orders_m.status) > _status_rank(existing.status):
        log.info(
            f"Membership: upgrade {existing.user.username} on {survivor.code} "
            f"{existing.status} → {orders_m.status} (from orders row)"
        )
        if apply:
            existing.status = orders_m.status
            existing.approved_by = orders_m.approved_by or existing.approved_by
            existing.approved_at = orders_m.approved_at or existing.approved_at
            if orders_m.status != TribeGroupMembership.STATUS_INACTIVE:
                existing.left_at = None
                existing.removed_by = None
            existing.history_changed_by = None
            existing.save()
    else:
        log.info(
            f"Membership: keep {existing.user.username} on {survivor.code} "
            f"({existing.status}); retire orders row ({orders_m.status})"
        )

    for mc in list(orders_m.characters.all()):
        if existing.characters.filter(character_id=mc.character_id).exists():
            log.info(
                f"Membership char: {mc.character} already on survivor; "
                f"drop from orders row"
            )
            if apply:
                mc.delete()
        else:
            log.info(
                f"Membership char: move {mc.character} → survivor membership"
            )
            if apply:
                mc.membership = existing
                mc.save(update_fields=["membership"])

    if apply:
        if orders_m.status != TribeGroupMembership.STATUS_INACTIVE:
            orders_m.status = TribeGroupMembership.STATUS_INACTIVE
            orders_m.left_at = timezone.now()
            orders_m.history_inactive_reason = "removed"
            orders_m.save()
        # Detach from orders group so the group can be deactivated empty of actives
        # Keep the inactive row pointing at orders until group deactivate, or
        # delete the duplicate inactive after move — unique is per tribe_group+user
        # so both can stay. Deactivate orders group with inactive memberships OK.


def _relocate_group_children(
    source: TribeGroup,
    survivor: TribeGroup,
    *,
    apply: bool,
    log: MergeLog,
) -> None:
    """Move requirements, activities, ranks, order M2M from source → survivor."""
    for req in TribeGroupRequirement.objects.filter(tribe_group=source):
        log.info(f"Requirement pk={req.pk}: {source.code} → {survivor.code}")
        if apply:
            req.tribe_group = survivor
            req.save(update_fields=["tribe_group"])

    for act in TribeGroupActivity.objects.filter(tribe_group=source):
        log.info(
            f"Activity pk={act.pk} type={act.activity_type}: "
            f"{source.code} → {survivor.code}"
        )
        if apply:
            act.tribe_group = survivor
            act.save(update_fields=["tribe_group"])

    for rank in TribeGroupRank.objects.filter(tribe_group=source):
        log.info(f"Rank {rank.name!r}: {source.code} → {survivor.code}")
        if apply:
            rank.tribe_group = survivor
            rank.save(update_fields=["tribe_group"])

    for order in IndustryOrder.objects.filter(tribe_groups=source):
        log.info(
            f"IndustryOrder pk={order.pk}: add {survivor.code}, "
            f"remove {source.code}"
        )
        if apply:
            order.tribe_groups.add(survivor)
            order.tribe_groups.remove(source)


def merge_contracts_and_orders(
    *,
    apply: bool,
    log: MergeLog,
    discord: DiscordClient | None,
) -> TribeGroup | None:
    """Merge market.contracts + market.market-orders (or already-merged supply.market)."""
    survivor = (
        TribeGroup.objects.filter(code="supply.market").first()
        or TribeGroup.objects.filter(code="market.contracts").first()
    )
    orders = TribeGroup.objects.filter(code="market.market-orders").first()

    if survivor is None:
        log.info("No Contracts / supply.market tribe group found")
        return None

    market_auth = _rename_auth_group(
        CONTRACTS_AUTH,
        MARKET_GROUP_AUTH,
        apply=apply,
        log=log,
        discord=discord,
    )
    # If contracts auth already renamed, resolve Market group auth
    if market_auth is None:
        market_auth = Group.objects.filter(name=MARKET_GROUP_AUTH).first()

    if market_auth and Group.objects.filter(name=ORDERS_AUTH).exists():
        _move_auth_members(ORDERS_AUTH, market_auth, apply=apply, log=log)

    if orders and orders.pk != survivor.pk:
        for m in TribeGroupMembership.objects.filter(
            tribe_group=orders
        ).select_related("user", "tribe_group", "rank"):
            _merge_membership_into_survivor(m, survivor, apply=apply, log=log)
        _relocate_group_children(orders, survivor, apply=apply, log=log)
        log.info(f"Deactivate tribe group {orders.code} (pk={orders.pk})")
        if apply:
            orders.is_active = False
            orders.group = None
            orders.chief = None
            orders.save()

    log.info(
        f"Survivor Market group: rename to Market / supply.market "
        f"(pk={survivor.pk}, was code={survivor.code!r})"
    )
    if apply:
        survivor.name = "Market"
        survivor.code = "supply.market"
        if market_auth and survivor.group_id != market_auth.pk:
            survivor.group = market_auth
        survivor.is_active = True
        survivor.save()
    return survivor


def rename_group_codes(*, apply: bool, log: MergeLog) -> None:
    for old, new in CODE_RENAMES.items():
        if old == "market.contracts":
            continue  # handled in merge_contracts_and_orders
        tg = TribeGroup.objects.filter(code=old).first()
        if not tg:
            if TribeGroup.objects.filter(code=new).exists():
                log.info(f"Code already {new!r}")
            else:
                log.info(f"TribeGroup code {old!r} not found (skip)")
            continue
        log.info(f"Code {old!r} → {new!r} (pk={tg.pk})")
        if apply:
            tg.code = new
            tg.save(update_fields=["code"])


def reparent_and_rename_tribes(
    *,
    apply: bool,
    log: MergeLog,
    supply_auth: Group | None,
) -> Tribe | None:
    industry = Tribe.objects.filter(slug="industry").first()
    supply = Tribe.objects.filter(slug="supply").first()
    market_tribe = Tribe.objects.filter(slug="market").first()

    if supply and industry and supply.pk != industry.pk:
        raise RuntimeError(
            "Both slug=industry and slug=supply exist; resolve manually."
        )

    target = supply or industry
    if not target:
        log.info("No Industry/Supply tribe found")
        return None

    log.info(
        f"Tribe pk={target.pk}: name/slug → Supply/supply "
        f"(was {target.name!r}/{target.slug!r})"
    )
    if apply:
        target.name = "Supply"
        target.slug = "supply"
        target.description = SUPPLY_DESCRIPTION or target.description
        if supply_auth:
            target.group = supply_auth
        target.is_active = True
        target.save()

    codes = set(CODE_RENAMES.keys()) | set(CODE_RENAMES.values())
    codes.add("market.market-orders")
    q = Q(code__in=codes) | Q(tribe=target)
    if market_tribe:
        q |= Q(tribe=market_tribe)
    groups = TribeGroup.objects.filter(q).distinct()

    for tg in groups:
        if tg.tribe_id != target.pk:
            log.info(
                f"Reparent {tg.code} pk={tg.pk} "
                f"tribe {tg.tribe_id} → {target.pk}"
            )
            if apply:
                tg.tribe = target
                tg.save(update_fields=["tribe"])

    if market_tribe and market_tribe.pk != target.pk:
        log.info(
            f"Deactivate Market tribe pk={market_tribe.pk} "
            f"(clear chief/group)"
        )
        if apply:
            market_tribe.is_active = False
            market_tribe.chief = None
            market_tribe.group = None
            market_tribe.save()

    return target


def run_merge_supply_tribe(*, apply: bool) -> MergeLog:
    """
    Execute (or dry-run) the full Industry+Market → Supply merge.

    When ``apply`` is False, only logs planned actions.

    Order matters for Discord/auth signals: reparent groups under Supply
    *before* merging memberships, so membership saves add ``Tribe - Supply``
    rather than re-adding ``Tribe - Market``.
    """
    log = MergeLog()
    mode = "APPLY" if apply else "DRY-RUN"
    log.info(f"=== merge_supply_tribe ({mode}) ===")

    discord = DiscordClient() if apply else None

    supply_auth = _rename_auth_group(
        INDUSTRY_AUTH,
        SUPPLY_AUTH,
        apply=apply,
        log=log,
        discord=discord,
    )
    if supply_auth is None:
        supply_auth = (
            Group.objects.filter(name=SUPPLY_AUTH).first()
            or Group.objects.filter(name=INDUSTRY_AUTH).first()
        )

    if supply_auth and Group.objects.filter(name=MARKET_AUTH).exists():
        _move_auth_members(MARKET_AUTH, supply_auth, apply=apply, log=log)
    else:
        log.info("No Tribe - Market auth to drain (or Supply missing)")

    # Reparent + rename tribe before membership merges (signal safety).
    reparent_and_rename_tribes(apply=apply, log=log, supply_auth=supply_auth)

    merge_contracts_and_orders(apply=apply, log=log, discord=discord)
    rename_group_codes(apply=apply, log=log)

    # Final: ensure survivor description for Market group if empty
    market_tg = TribeGroup.objects.filter(code="supply.market").first()
    if market_tg and apply and not market_tg.description:
        market_tg.description = (
            "Contracts and market orders — doctrine fits, seed stock, "
            "and the alliance market pipeline."
        )
        market_tg.save(update_fields=["description"])

    # Membership signals can briefly re-add retired tribe auth; drain again.
    if supply_auth and Group.objects.filter(name=MARKET_AUTH).exists():
        _move_auth_members(MARKET_AUTH, supply_auth, apply=apply, log=log)

    retired = [MARKET_AUTH, ORDERS_AUTH, INDUSTRY_AUTH, CONTRACTS_AUTH]
    for name in retired:
        g = Group.objects.filter(name=name).first()
        if g:
            n = g.user_set.count()
            log.info(f"Post-check: {name!r} still has {n} user(s)")

    supply = Tribe.objects.filter(slug="supply", is_active=True).first()
    if supply:
        active_groups = list(
            TribeGroup.objects.filter(tribe=supply, is_active=True)
            .order_by("code")
            .values_list("code", flat=True)
        )
        log.info(
            f"Active Supply groups ({len(active_groups)}): {active_groups}"
        )

    log.info(f"=== done ({mode}) ===")
    return log
