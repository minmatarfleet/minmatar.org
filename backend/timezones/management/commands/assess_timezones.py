from collections import Counter

from django.core.management.base import BaseCommand

from timezones import discord_roles, services


class Command(BaseCommand):
    help = (
        "Assess pilot timezones now and sync their Discord roles. "
        "--dry-run prints what would be stored without saving or touching "
        "Discord."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user", type=int, action="append", help="User id (repeatable)"
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        results = services.assess_users(options["user"], save=not dry_run)
        eligible = services.eligible_user_ids(results)
        brackets = Counter()
        sources = Counter()
        for user_id, result in results.items():
            sources[result.home_source or "none"] += 1
            if user_id in eligible:
                brackets.update(result.brackets)
            if options["user"]:
                self.stdout.write(
                    f"user {user_id}: home={result.home} "
                    f"({result.home_source}, inferred={result.inferred_home} "
                    f"P={result.inferred_confidence}) "
                    f"brackets={sorted(result.brackets)} "
                    f"active_days={result.active_days} "
                    f"evenings={result.evenings}"
                )
        self.stdout.write(f"Assessed {len(results)} pilots")
        self.stdout.write(f"Home from: {dict(sources)}")
        self.stdout.write(f"Eligible pilots per bracket: {dict(brackets)}")
        if dry_run:
            self.stdout.write("Dry run: nothing saved, no roles changed")
            return
        self.stdout.write(
            f"Roles: {dict(discord_roles.apply_roles(options['user']))}"
        )
