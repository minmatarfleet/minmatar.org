"""
Fetch corporation roles from ESI and print them (for debugging recruiter/director sync).

Requires a director or CEO of the corporation to have logged in with
esi-corporations.read_corporation_membership.v1. Title-granted roles are
included when a director also has esi-corporations.read_titles.v1.

Usage:
  pipenv run python manage.py corporation_roles_esi 98696436
  pipenv run python manage.py corporation_roles_esi 98696436 --character "C0ach Gar0f"
  pipenv run python manage.py corporation_roles_esi 98696436 --character "C0ach"
"""

from django.core.management.base import BaseCommand

from eveonline.client import EsiClient
from eveonline.helpers.corporations.update import (
    SCOPE_CORPORATION_MEMBERSHIP,
    SCOPE_CORPORATION_TITLES,
    _all_roles_for_member,
    _fetch_title_granted_roles,
    get_director_with_scope,
)
from eveonline.models import EveCorporation


class Command(BaseCommand):
    help = "Fetch corporation roles from ESI and print (for debugging recruiter sync)."

    def add_arguments(self, parser):
        parser.add_argument(
            "corporation_id",
            type=int,
            help="EVE corporation ID (e.g. 98696436 for Minmatar Fleet Academy).",
        )
        parser.add_argument(
            "--character",
            type=str,
            help="Optional: filter to entries whose character name contains this (case-insensitive).",
        )

    def handle(self, *args, **options):
        corporation_id = options["corporation_id"]
        character_filter = (options.get("character") or "").strip()

        corporation = EveCorporation.objects.filter(
            corporation_id=corporation_id
        ).first()
        if not corporation:
            self.stdout.write(
                self.style.WARNING(
                    f"Corporation {corporation_id} not in DB. Run populate first."
                )
            )
            return

        character = get_director_with_scope(
            corporation, SCOPE_CORPORATION_MEMBERSHIP
        )
        if not character:
            self.stdout.write(
                self.style.ERROR(
                    f"No director/CEO with esi-corporations.read_corporation_membership.v1 "
                    f"for {corporation.name} ({corporation_id}). "
                    "They must log in so we can call ESI."
                )
            )
            return

        self.stdout.write(
            f"Using token for {character.character_name} (character_id={character.character_id})"
        )

        esi_roles = EsiClient(character).get_corporation_roles(corporation_id)
        if not esi_roles.success():
            self.stdout.write(
                self.style.ERROR(
                    f"ESI roles failed: {esi_roles.response_code} {esi_roles.error_text()}"
                )
            )
            return

        roles_data = esi_roles.results() or []
        self.stdout.write(
            f"ESI returned {len(roles_data)} role entries (all pages)."
        )

        title_roles_by_character = _fetch_title_granted_roles(
            corporation, character
        )
        if title_roles_by_character:
            self.stdout.write(
                f"Loaded title grants for {len(title_roles_by_character)} members "
                f"(requires {SCOPE_CORPORATION_TITLES[0]})."
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "No title grants loaded (missing titles scope or ESI error); "
                    "showing direct roles only."
                )
            )

        if not roles_data and not title_roles_by_character:
            self.stdout.write("No role entries.")
            return

        roles_by_character = {
            entry.get("character_id"): entry
            for entry in roles_data
            if entry.get("character_id") is not None
        }
        character_ids = sorted(
            set(roles_by_character) | set(title_roles_by_character)
        )

        try:
            resolved = EsiClient(None).resolve_universe_names(character_ids)
            id_to_name = {r["id"]: r["name"] for r in resolved.results()}
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Resolve names failed: {e}"))
            id_to_name = {}

        for char_id in character_ids:
            name = id_to_name.get(char_id, f"<id={char_id}>")
            if (
                character_filter
                and character_filter.lower() not in name.lower()
            ):
                continue
            entry = roles_by_character.get(char_id) or {}
            direct_roles = _all_roles_for_member(entry)
            title_roles = title_roles_by_character.get(char_id, set())
            all_roles = direct_roles | title_roles
            has_personnel_manager = "Personnel_Manager" in all_roles
            self.stdout.write("")
            self.stdout.write(f"  character_id={char_id}  name={name!r}")
            self.stdout.write(f"    roles: {sorted(entry.get('roles') or [])}")
            self.stdout.write(
                f"    roles_at_hq: {sorted(entry.get('roles_at_hq') or [])}"
            )
            self.stdout.write(
                f"    roles_at_base: {sorted(entry.get('roles_at_base') or [])}"
            )
            self.stdout.write(
                f"    roles_at_other: {sorted(entry.get('roles_at_other') or [])}"
            )
            self.stdout.write(f"    title_granted: {sorted(title_roles)}")
            self.stdout.write(
                f"    effective (roles + titles, used by sync): {sorted(all_roles)}"
            )
            if has_personnel_manager:
                self.stdout.write(
                    self.style.SUCCESS(
                        "    Personnel_Manager effective? Yes → would be recruiter in app"
                    )
                )
            else:
                self.stdout.write(
                    "    Personnel_Manager effective? No → would NOT be recruiter in app"
                )

        self.stdout.write("")
