"""Sync PilotFeature rows from the code registry."""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from groups.features.registry import FEATURE_DEFINITIONS
from groups.models import AffiliationType, PilotFeature
from tribes.models import TribeGroup


class Command(BaseCommand):
    help = "Upsert PilotFeature rows from the code registry and seed default wiring."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        warnings: list[str] = []

        for definition in FEATURE_DEFINITIONS.values():
            feature, was_created = PilotFeature.objects.update_or_create(
                code=definition.code,
                defaults={
                    "label": definition.label,
                    "description": definition.description,
                    "scope": definition.scope,
                    "legacy_permission": definition.legacy_permission,
                    "staff_permission": definition.staff_permission,
                    "deny_community_statuses": list(
                        definition.deny_community_statuses
                    ),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

            if definition.default_affiliation_names and not feature.affiliations.exists():
                for name in definition.default_affiliation_names:
                    affiliation = AffiliationType.objects.filter(
                        name=name
                    ).first()
                    if affiliation is None:
                        warnings.append(
                            f"AffiliationType '{name}' not found for {definition.code}"
                        )
                        continue
                    feature.affiliations.add(affiliation)

            if definition.default_tribe_group_codes and not feature.tribe_groups.exists():
                for code in definition.default_tribe_group_codes:
                    tribe_group = TribeGroup.objects.filter(code=code).first()
                    if tribe_group is None:
                        warnings.append(
                            f"TribeGroup '{code}' not found for {definition.code}"
                        )
                        continue
                    feature.tribe_groups.add(tribe_group)

            if definition.default_auth_group_names and not feature.auth_groups.exists():
                for group_name in definition.default_auth_group_names:
                    auth_group = Group.objects.filter(name=group_name).first()
                    if auth_group is None:
                        warnings.append(
                            f"auth.Group '{group_name}' not found for {definition.code}"
                        )
                        continue
                    feature.auth_groups.add(auth_group)

            if definition.code == "tribes.apply" and not feature.tribe_groups.exists():
                for tribe_group in TribeGroup.objects.filter(is_active=True):
                    feature.tribe_groups.add(tribe_group)

        for warning in warnings:
            self.stdout.write(self.style.WARNING(warning))

        self.stdout.write(
            self.style.SUCCESS(
                f"sync_pilot_features: {created} created, {updated} updated."
            )
        )
