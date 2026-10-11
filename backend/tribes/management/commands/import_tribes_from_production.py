"""
Copy tribes catalog (tribes, groups, chiefs, auth groups, ranks, requirements,
memberships) from production_readonly into the local default database.

Preserves Tribe / TribeGroup / Requirement / Rank primary keys so local URLs
match production. Auth Groups are matched by name; Users by username.
EveCharacters are matched by character_id.

Production may lag schema (e.g. missing TribeGroup.content) — those fields
are deferred on read and left blank locally when absent.

Usage (from backend/, with DB_READONLY_* / production_readonly configured):

    pipenv run python manage.py import_tribes_from_production --clear
    pipenv run python manage.py import_tribes_from_production --clear --dry-run
    pipenv run python manage.py import_tribes_from_production --clear --skip-memberships
"""

from __future__ import annotations

from contextlib import contextmanager

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import signals

from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
)
from discord.models import DiscordRole
from eveonline.helpers.production_import import (
    assert_local_has_eve_types,
    validate_source_alias,
)
from eveonline.models import EveCharacter, EveLocation, EvePlayer
from eveonline.signals import (
    populate_eve_character_private_data,
    populate_eve_character_public_data,
)
from help_tickets.models import HelpRequestCategory
from posts.models import EvePost
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
    TribeGroupMembershipHistory,
    TribeGroupRank,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
    TribeGroupRequirementSkill,
)

USER_COPY_FIELDS = (
    "password",
    "last_login",
    "is_superuser",
    "first_name",
    "last_name",
    "email",
    "is_staff",
    "is_active",
    "date_joined",
)

CHARACTER_COPY_FIELDS = (
    "character_name",
    "corporation_id",
    "alliance_id",
    "faction_id",
    "security_status",
    "exempt",
    "esi_suspended",
    "esi_deleted",
    "esi_deleted_at",
    "esi_token_level",
    "esi_scope_groups",
    "medical_clone_location_id",
    "medical_clone_location_name",
    "active_implants",
)


@contextmanager
def _muted_signals():
    """Disable membership / character / Discord side effects during bulk import."""
    # pylint: disable-next=import-outside-toplevel
    from tribes.signals import (
        tribe_group_membership_post_save,
        tribe_group_membership_pre_save,
    )

    pairs = [
        (
            signals.pre_save,
            TribeGroupMembership,
            tribe_group_membership_pre_save,
            "tribe_group_membership_pre_save",
        ),
        (
            signals.post_save,
            TribeGroupMembership,
            tribe_group_membership_post_save,
            "tribe_group_membership_post_save",
        ),
        (
            signals.post_save,
            EveCharacter,
            populate_eve_character_public_data,
            "populate_eve_character_public_data",
        ),
        (
            signals.post_save,
            EveCharacter,
            populate_eve_character_private_data,
            "populate_eve_character_private_data",
        ),
        (
            signals.post_save,
            Group,
            group_post_save,
            "group_post_save",
        ),
        (
            signals.pre_save,
            DiscordRole,
            resolve_existing_discord_role_from_server,
            "resolve_existing_discord_role_from_server",
        ),
    ]
    for signal, sender, _, uid in pairs:
        signal.disconnect(sender=sender, dispatch_uid=uid)
    try:
        yield
    finally:
        for signal, sender, receiver, uid in pairs:
            signal.connect(receiver, sender=sender, dispatch_uid=uid)


class Command(BaseCommand):
    help = (
        "Import tribes, groups, chiefs, ranks, requirements, and memberships "
        "from production_readonly into the local default database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="production_readonly",
            help="Django DB alias to read from (default: production_readonly).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Wipe local tribe memberships / requirements / groups / tribes "
                "before import (recommended for an exact mirror)."
            ),
        )
        parser.add_argument(
            "--skip-memberships",
            action="store_true",
            help="Import catalog + chiefs only; skip memberships and history.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print planned work without writing.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        validate_source_alias(source, local)

        tribes = list(
            Tribe.objects.using(source)
            .select_related("chief", "group")
            .order_by("pk")
        )
        # Prod may not have TribeGroup.content yet.
        groups = list(
            TribeGroup.objects.using(source)
            .defer("content")
            .select_related("tribe", "chief", "group")
            .order_by("pk")
        )
        ranks = list(
            TribeGroupRank.objects.using(source)
            .select_related("group")
            .order_by("pk")
        )
        requirements = list(
            TribeGroupRequirement.objects.using(source).order_by("pk")
        )
        req_skills = list(
            TribeGroupRequirementSkill.objects.using(source).order_by("pk")
        )
        req_assets = list(
            TribeGroupRequirementAssetType.objects.using(source)
            .prefetch_related("locations")
            .order_by("pk")
        )

        memberships: list[TribeGroupMembership] = []
        membership_chars: list[TribeGroupMembershipCharacter] = []
        membership_history: list[TribeGroupMembershipHistory] = []
        membership_char_history: list[TribeGroupMembershipCharacterHistory] = (
            []
        )
        if not options["skip_memberships"]:
            memberships = list(
                TribeGroupMembership.objects.using(source)
                .select_related("user")
                .order_by("pk")
            )
            membership_chars = list(
                TribeGroupMembershipCharacter.objects.using(source)
                .select_related("character")
                .order_by("pk")
            )
            membership_history = list(
                TribeGroupMembershipHistory.objects.using(source).order_by(
                    "pk"
                )
            )
            membership_char_history = list(
                TribeGroupMembershipCharacterHistory.objects.using(source)
                .select_related("character")
                .order_by("pk")
            )

        type_ids = {
            row.eve_type_id for row in req_skills if row.eve_type_id
        } | {row.eve_type_id for row in req_assets if row.eve_type_id}
        assert_local_has_eve_types(
            type_ids,
            local,
            hint="Load eveuniverse data locally first.",
        )

        location_ids: set[int] = set()
        for asset in req_assets:
            location_ids.update(asset.locations.values_list("pk", flat=True))

        auth_group_ids = {
            *(t.group_id for t in tribes if t.group_id),
            *(g.group_id for g in groups if g.group_id),
            *(r.group_id for r in ranks if r.group_id),
        }
        chief_user_ids = {
            *(t.chief_id for t in tribes if t.chief_id),
            *(g.chief_id for g in groups if g.chief_id),
        }
        member_user_ids = {m.user_id for m in memberships}
        member_user_ids.update(
            m.approved_by_id for m in memberships if m.approved_by_id
        )
        member_user_ids.update(
            m.removed_by_id for m in memberships if m.removed_by_id
        )
        member_user_ids.update(
            h.changed_by_id for h in membership_history if h.changed_by_id
        )
        member_user_ids.update(
            h.by_id for h in membership_char_history if h.by_id
        )
        all_user_ids = chief_user_ids | member_user_ids

        character_ids = {
            mc.character.character_id for mc in membership_chars
        } | {
            h.character.character_id
            for h in membership_char_history
            if h.character_id
        }

        self.stdout.write(
            f"Source={source}: {len(tribes)} tribes, {len(groups)} groups, "
            f"{len(ranks)} ranks, {len(requirements)} requirements, "
            f"{len(req_skills)} skills, {len(req_assets)} assets, "
            f"{len(memberships)} memberships, "
            f"{len(membership_chars)} membership characters, "
            f"{len(auth_group_ids)} auth groups, "
            f"{len(all_user_ids)} users, {len(character_ids)} characters."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        if not options["clear"]:
            raise CommandError(
                "Refusing to import without --clear (local PKs / orphans "
                "would diverge from production). Pass --clear to wipe local "
                "tribe data first."
            )

        with _muted_signals():
            with transaction.atomic(using=local):
                self._clear_local(local)
                auth_map = self._ensure_auth_groups(
                    source, local, auth_group_ids
                )
                user_map = self._ensure_users(source, local, all_user_ids)
                self._ensure_characters(source, local, character_ids, user_map)
                # Primaries for chiefs + all members so roster/PilotBadge resolve.
                self._ensure_primary_characters(
                    source, local, all_user_ids, user_map
                )
                self._ensure_locations(source, local, location_ids)
                self._import_tribes(tribes, local, auth_map, user_map)
                self._import_groups(groups, local, auth_map, user_map)
                self._import_ranks(ranks, local, auth_map)
                self._import_requirements(
                    requirements, req_skills, req_assets, local
                )
                if not options["skip_memberships"]:
                    self._import_memberships(
                        memberships,
                        membership_chars,
                        membership_history,
                        membership_char_history,
                        local,
                        user_map,
                    )
                    # Celery remove_tribe_members_without_permission checks
                    # tribes.apply (legacy perm) without tribe_group context.
                    self._grant_tribes_apply_permission(
                        local, set(user_map.values())
                    )

        self._print_summary(local)

    def _clear_local(self, local: str) -> None:
        # Detach help categories so CASCADE delete of TribeGroup is not blocked
        # by HelpTicket → HelpRequestCategory PROTECT.
        detached = (
            HelpRequestCategory.objects.using(local)
            .exclude(tribe_group_id=None)
            .update(tribe_group_id=None)
        )
        if detached:
            self.stdout.write(
                self.style.WARNING(
                    f"  Detached HelpRequestCategory.tribe_group ({detached})."
                )
            )

        # Clear posts M2M so orphaned through-rows do not linger.
        through = EvePost.tribe_groups.through
        m2m_deleted, _ = through.objects.using(local).all().delete()
        if m2m_deleted:
            self.stdout.write(
                self.style.WARNING(
                    f"  Cleared EvePost.tribe_groups links ({m2m_deleted})."
                )
            )

        order = [
            (
                "TribeGroupMembershipCharacterHistory",
                TribeGroupMembershipCharacterHistory,
            ),
            ("TribeGroupMembershipHistory", TribeGroupMembershipHistory),
            ("TribeGroupMembershipCharacter", TribeGroupMembershipCharacter),
            ("TribeGroupMembership", TribeGroupMembership),
            ("TribeGroupRequirementSkill", TribeGroupRequirementSkill),
            ("TribeGroupRequirementAssetType", TribeGroupRequirementAssetType),
            ("TribeGroupRequirement", TribeGroupRequirement),
            ("TribeGroupRank", TribeGroupRank),
            ("TribeGroup", TribeGroup),
            ("Tribe", Tribe),
        ]
        for label, model in order:
            deleted, _ = model.objects.using(local).all().delete()
            self.stdout.write(
                self.style.WARNING(f"  Cleared {label} ({deleted}).")
            )

    def _ensure_auth_groups(
        self, source: str, local: str, group_ids: set[int]
    ) -> dict[int, int]:
        """Map production auth.Group pk → local pk (match by name)."""
        mapping: dict[int, int] = {}
        if not group_ids:
            return mapping
        prod_groups = list(
            Group.objects.using(source).filter(pk__in=group_ids).order_by("pk")
        )
        for prod in prod_groups:
            local_group, created = Group.objects.using(local).get_or_create(
                name=prod.name
            )
            mapping[prod.pk] = local_group.pk
            action = "created" if created else "matched"
            self.stdout.write(
                f"  Auth Group {prod.name!r}: {action} → local id={local_group.pk}"
            )
        return mapping

    def _ensure_users(
        self, source: str, local: str, user_ids: set[int]
    ) -> dict[int, int]:
        """Map production User pk → local pk (match by username)."""
        mapping: dict[int, int] = {}
        if not user_ids:
            return mapping
        prod_users = list(
            User.objects.using(source).filter(pk__in=user_ids).order_by("pk")
        )
        created = 0
        matched = 0
        for prod in prod_users:
            local_user = (
                User.objects.using(local)
                .filter(username=prod.username)
                .first()
            )
            if local_user is None:
                # Prefer preserving production PK when free.
                if not User.objects.using(local).filter(pk=prod.pk).exists():
                    local_user = User(pk=prod.pk, username=prod.username)
                else:
                    local_user = User(username=prod.username)
                for field in USER_COPY_FIELDS:
                    setattr(local_user, field, getattr(prod, field))
                local_user.save(using=local)
                created += 1
            else:
                matched += 1
            mapping[prod.pk] = local_user.pk
        self.stdout.write(
            f"  Users: matched={matched} created={created} mapped={len(mapping)}"
        )
        return mapping

    def _ensure_characters(
        self,
        source: str,
        local: str,
        character_ids: set[int],
        user_map: dict[int, int],
    ) -> None:
        if not character_ids:
            return
        prod_chars = list(
            EveCharacter.objects.using(source)
            .filter(character_id__in=character_ids)
            .order_by("character_id")
        )
        created = 0
        updated = 0
        for prod in prod_chars:
            local_user_id = None
            if prod.user_id and prod.user_id in user_map:
                local_user_id = user_map[prod.user_id]
            existing = (
                EveCharacter.objects.using(local)
                .filter(character_id=prod.character_id)
                .first()
            )
            if existing is None:
                char = EveCharacter(character_id=prod.character_id)
                for field in CHARACTER_COPY_FIELDS:
                    setattr(char, field, getattr(prod, field))
                char.user_id = local_user_id
                char.token = None
                char.save(using=local)
                created += 1
            else:
                for field in CHARACTER_COPY_FIELDS:
                    setattr(existing, field, getattr(prod, field))
                if local_user_id and existing.user_id != local_user_id:
                    existing.user_id = local_user_id
                existing.save(using=local)
                updated += 1
        self.stdout.write(
            f"  EveCharacters: created={created} updated={updated}"
        )

    def _ensure_primary_characters(
        self,
        source: str,
        local: str,
        prod_user_ids: set[int],
        user_map: dict[int, int],
    ) -> None:
        """Ensure each user has a primary EveCharacter locally for roster display."""
        if not prod_user_ids:
            return

        # Resolve production primary (or first character) per user, then batch-copy.
        primary_by_prod_user: dict[int, int] = {}
        for prod_user_id in prod_user_ids:
            prod_player = (
                EvePlayer.objects.using(source)
                .filter(user_id=prod_user_id)
                .select_related("primary_character")
                .first()
            )
            primary = (
                prod_player.primary_character
                if prod_player and prod_player.primary_character_id
                else None
            )
            if primary is None:
                primary = (
                    EveCharacter.objects.using(source)
                    .filter(user_id=prod_user_id)
                    .order_by("character_id")
                    .first()
                )
            if primary is not None:
                primary_by_prod_user[prod_user_id] = primary.character_id

        self._ensure_characters(
            source, local, set(primary_by_prod_user.values()), user_map
        )

        char_pk_by_eve_id = {
            c.character_id: c
            for c in EveCharacter.objects.using(local).filter(
                character_id__in=set(primary_by_prod_user.values())
            )
        }

        ensured = 0
        skipped = 0
        for prod_user_id, eve_char_id in primary_by_prod_user.items():
            local_user_id = user_map.get(prod_user_id)
            local_char = char_pk_by_eve_id.get(eve_char_id)
            if not local_user_id or local_char is None:
                skipped += 1
                continue
            if local_char.user_id != local_user_id:
                local_char.user_id = local_user_id
                local_char.save(using=local)

            local_user = User.objects.using(local).get(pk=local_user_id)
            player, _ = EvePlayer.objects.using(local).get_or_create(
                user=local_user,
                defaults={"nickname": local_user.username},
            )
            if player.primary_character_id == local_char.pk:
                ensured += 1
                continue

            # primary_character is unique — clear any other local claim first.
            EvePlayer.objects.using(local).filter(
                primary_character_id=local_char.pk
            ).exclude(pk=player.pk).update(primary_character_id=None)

            player.primary_character = local_char
            if not player.nickname:
                player.nickname = local_user.username
            player.save(using=local)
            ensured += 1

        self.stdout.write(
            f"  EvePlayer primaries: ensured={ensured} skipped={skipped}"
        )

    def _grant_tribes_apply_permission(
        self, local: str, local_user_ids: set[int]
    ) -> None:
        """Grant legacy tribes.apply so cleanup tasks do not wipe imported actives."""
        if not local_user_ids:
            return
        perm = (
            Permission.objects.using(local)
            .filter(
                content_type__app_label="tribes",
                codename="add_tribegroupmembership",
            )
            .first()
        )
        if perm is None:
            self.stdout.write(
                self.style.WARNING(
                    "  Could not find tribes.add_tribegroupmembership; "
                    "Celery may deactivate imported memberships."
                )
            )
            return
        users = list(User.objects.using(local).filter(pk__in=local_user_ids))
        for user in users:
            user.user_permissions.add(perm)
        self.stdout.write(
            f"  Granted tribes.add_tribegroupmembership to {len(users)} users"
        )

    def _ensure_locations(
        self, source: str, local: str, location_ids: set[int]
    ) -> None:
        if not location_ids:
            return
        missing = set(location_ids) - set(
            EveLocation.all_objects.using(local)
            .filter(pk__in=location_ids)
            .values_list("pk", flat=True)
        )
        if not missing:
            return
        skip = frozenset({"location_id", "deleted", "deleted_by_cascade"})
        for loc in EveLocation.objects.using(source).filter(pk__in=missing):
            fields = {
                f.name: getattr(loc, f.name)
                for f in EveLocation._meta.concrete_fields  # pylint: disable=protected-access
                if f.name not in skip
            }
            EveLocation(location_id=loc.pk, **fields).save(using=local)
            self.stdout.write(
                f"  Copied EveLocation {loc.pk} ({loc.location_name})"
            )

    def _import_tribes(self, tribes, local, auth_map, user_map) -> None:
        for prod in tribes:
            Tribe.objects.using(local).update_or_create(
                pk=prod.pk,
                defaults={
                    "name": prod.name,
                    "slug": prod.slug,
                    "description": prod.description,
                    "content": prod.content or "",
                    "image_url": prod.image_url,
                    "banner_url": prod.banner_url,
                    "discord_channel_id": prod.discord_channel_id,
                    "is_active": prod.is_active,
                    "group_id": (
                        auth_map.get(prod.group_id) if prod.group_id else None
                    ),
                    "chief_id": (
                        user_map.get(prod.chief_id) if prod.chief_id else None
                    ),
                },
            )
        self.stdout.write(f"  Tribes: upserted={len(tribes)}")

    def _import_groups(self, groups, local, auth_map, user_map) -> None:
        for prod in groups:
            content = ""
            # Only copy content when the deferred field was actually loaded.
            if "content" not in getattr(prod, "get_deferred_fields")():
                content = prod.content or ""
            TribeGroup.objects.using(local).update_or_create(
                pk=prod.pk,
                defaults={
                    "tribe_id": prod.tribe_id,
                    "name": prod.name,
                    "code": prod.code,
                    "description": prod.description,
                    "content": content,
                    "discord_channel_id": prod.discord_channel_id,
                    "is_active": prod.is_active,
                    "required_token_type": prod.required_token_type or "",
                    "require_off_trial": bool(
                        getattr(prod, "require_off_trial", False)
                    ),
                    "group_id": (
                        auth_map.get(prod.group_id) if prod.group_id else None
                    ),
                    "chief_id": (
                        user_map.get(prod.chief_id) if prod.chief_id else None
                    ),
                },
            )
        self.stdout.write(f"  TribeGroups: upserted={len(groups)}")

    def _import_ranks(self, ranks, local, auth_map) -> None:
        for prod in ranks:
            TribeGroupRank.objects.using(local).update_or_create(
                pk=prod.pk,
                defaults={
                    "tribe_group_id": prod.tribe_group_id,
                    "name": prod.name,
                    "code": prod.code,
                    "sort_order": prod.sort_order,
                    "group_id": (
                        auth_map.get(prod.group_id) if prod.group_id else None
                    ),
                },
            )
        self.stdout.write(f"  Ranks: upserted={len(ranks)}")

    def _import_requirements(
        self, requirements, req_skills, req_assets, local
    ) -> None:
        for prod in requirements:
            TribeGroupRequirement.objects.using(local).update_or_create(
                pk=prod.pk,
                defaults={"tribe_group_id": prod.tribe_group_id},
            )
        for prod in req_skills:
            TribeGroupRequirementSkill.objects.using(local).update_or_create(
                pk=prod.pk,
                defaults={
                    "requirement_id": prod.requirement_id,
                    "eve_type_id": prod.eve_type_id,
                    "minimum_level": prod.minimum_level,
                },
            )
        for prod in req_assets:
            local_asset, _ = TribeGroupRequirementAssetType.objects.using(
                local
            ).update_or_create(
                pk=prod.pk,
                defaults={
                    "requirement_id": prod.requirement_id,
                    "eve_type_id": prod.eve_type_id,
                },
            )
            location_pks = list(prod.locations.values_list("pk", flat=True))
            local_asset.locations.set(location_pks)
        self.stdout.write(
            f"  Requirements: {len(requirements)} "
            f"(skills={len(req_skills)} assets={len(req_assets)})"
        )

    def _import_memberships(
        self,
        memberships,
        membership_chars,
        membership_history,
        membership_char_history,
        local,
        user_map,
    ) -> None:
        # Bulk insert with preserved PKs; signals are muted.
        membership_objs = []
        for prod in memberships:
            local_user_id = user_map.get(prod.user_id)
            if not local_user_id:
                continue
            membership_objs.append(
                TribeGroupMembership(
                    pk=prod.pk,
                    user_id=local_user_id,
                    tribe_group_id=prod.tribe_group_id,
                    rank_id=prod.rank_id,
                    status=prod.status,
                    requirement_snapshot=prod.requirement_snapshot,
                    created_at=prod.created_at,
                    approved_by_id=(
                        user_map.get(prod.approved_by_id)
                        if prod.approved_by_id
                        else None
                    ),
                    approved_at=prod.approved_at,
                    left_at=prod.left_at,
                    removed_by_id=(
                        user_map.get(prod.removed_by_id)
                        if prod.removed_by_id
                        else None
                    ),
                )
            )
        TribeGroupMembership.objects.using(local).bulk_create(
            membership_objs, batch_size=500
        )

        char_by_eve_id = {
            c.character_id: c.pk
            for c in EveCharacter.objects.using(local).filter(
                character_id__in={
                    mc.character.character_id for mc in membership_chars
                }
            )
        }
        membership_char_objs = []
        for prod in membership_chars:
            char_pk = char_by_eve_id.get(prod.character.character_id)
            if not char_pk:
                continue
            if (
                not TribeGroupMembership.objects.using(local)
                .filter(pk=prod.membership_id)
                .exists()
            ):
                continue
            membership_char_objs.append(
                TribeGroupMembershipCharacter(
                    pk=prod.pk,
                    membership_id=prod.membership_id,
                    character_id=char_pk,
                )
            )
        TribeGroupMembershipCharacter.objects.using(local).bulk_create(
            membership_char_objs, batch_size=500
        )

        history_objs = []
        for prod in membership_history:
            if (
                not TribeGroupMembership.objects.using(local)
                .filter(pk=prod.membership_id)
                .exists()
            ):
                continue
            history_objs.append(
                TribeGroupMembershipHistory(
                    pk=prod.pk,
                    membership_id=prod.membership_id,
                    from_status=prod.from_status,
                    to_status=prod.to_status,
                    changed_at=prod.changed_at,
                    changed_by_id=(
                        user_map.get(prod.changed_by_id)
                        if prod.changed_by_id
                        else None
                    ),
                    reason=prod.reason,
                )
            )
        TribeGroupMembershipHistory.objects.using(local).bulk_create(
            history_objs, batch_size=500
        )

        char_hist_by_eve = {
            c.character_id: c.pk
            for c in EveCharacter.objects.using(local).filter(
                character_id__in={
                    h.character.character_id
                    for h in membership_char_history
                    if h.character_id
                }
            )
        }
        char_history_objs = []
        for prod in membership_char_history:
            char_pk = char_hist_by_eve.get(
                prod.character.character_id if prod.character_id else None
            )
            if not char_pk:
                continue
            if (
                not TribeGroupMembership.objects.using(local)
                .filter(pk=prod.membership_id)
                .exists()
            ):
                continue
            char_history_objs.append(
                TribeGroupMembershipCharacterHistory(
                    pk=prod.pk,
                    membership_id=prod.membership_id,
                    character_id=char_pk,
                    action=prod.action,
                    at=prod.at,
                    by_id=user_map.get(prod.by_id) if prod.by_id else None,
                    leave_reason=prod.leave_reason,
                )
            )
        TribeGroupMembershipCharacterHistory.objects.using(local).bulk_create(
            char_history_objs, batch_size=500
        )

        self.stdout.write(
            f"  Memberships: {len(membership_objs)} "
            f"(chars={len(membership_char_objs)} "
            f"history={len(history_objs)} "
            f"char_history={len(char_history_objs)})"
        )

    def _print_summary(self, local: str) -> None:
        tribes = list(
            Tribe.objects.using(local).select_related("chief").order_by("pk")
        )
        groups = list(
            TribeGroup.objects.using(local)
            .select_related("tribe", "chief")
            .order_by("tribe_id", "pk")
        )
        self.stdout.write(
            self.style.SUCCESS("Import complete. Local catalog:")
        )
        for tribe in tribes:
            chief = tribe.chief.username if tribe.chief_id else None
            self.stdout.write(
                f"  Tribe {tribe.pk} {tribe.slug} active={tribe.is_active} "
                f"chief={chief!r}"
            )
        for group in groups:
            chief = group.chief.username if group.chief_id else None
            self.stdout.write(
                f"    Group {group.pk} {group.code} active={group.is_active} "
                f"chief={chief!r}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Counts: tribes={Tribe.objects.using(local).count()} "
                f"groups={TribeGroup.objects.using(local).count()} "
                f"memberships={TribeGroupMembership.objects.using(local).count()}"
            )
        )
