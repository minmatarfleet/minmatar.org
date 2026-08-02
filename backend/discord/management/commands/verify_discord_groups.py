"""Manually run live Discord ↔ Django fail-closed verification (test guild only)."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from discord.live_verify import (
    ALLOWED_LIVE_VERIFY_GUILD_IDS,
    LiveVerifyError,
    run_live_discord_groups_verify,
)


class Command(BaseCommand):
    help = (
        "Live OPSEC verification of fail-closed auth.Group ↔ Discord role sync. "
        "Refuses production guild IDs. Requires --i-understand-this-hits-live-discord. "
        "See docs/auth/discord-groups-verification.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help=(
                "Django username of a guild-linked subject "
                "(e.g. bearthatcares on the test server). Never offboarded."
            ),
        )
        parser.add_argument(
            "--i-understand-this-hits-live-discord",
            action="store_true",
            dest="confirm_live",
            help="Required confirmation that this will call the live Discord API.",
        )
        parser.add_argument(
            "--cases",
            default="",
            help="Comma-separated case IDs (e.g. A1,A2,B1). Default: full matrix.",
        )
        parser.add_argument(
            "--burst-count",
            type=int,
            default=20,
            help="Number of VERIFY-Burst-* roles for F1/F2 (default 20).",
        )
        parser.add_argument(
            "--guild-id",
            type=int,
            default=None,
            help=(
                "Override settings.DISCORD_GUILD_ID for this run "
                "(must be an allowlisted test guild; production always refused)."
            ),
        )
        parser.add_argument(
            "--allow-guild-id",
            type=int,
            action="append",
            default=[],
            dest="allow_guild_ids",
            help=(
                "Extra non-production guild ID to allow (repeatable). "
                f"Default allowlist: {sorted(ALLOWED_LIVE_VERIFY_GUILD_IDS)}"
            ),
        )

    def handle(self, *args, **options):
        if not options["confirm_live"]:
            raise CommandError(
                "Refusing to run without "
                "--i-understand-this-hits-live-discord"
            )

        case_ids = None
        raw_cases = (options["cases"] or "").strip()
        if raw_cases:
            case_ids = {
                part.strip().upper()
                for part in raw_cases.split(",")
                if part.strip()
            }

        extra = frozenset(options["allow_guild_ids"] or [])
        try:
            report = run_live_discord_groups_verify(
                username=options["username"],
                require_env=False,
                allow_extra_guild_ids=extra or None,
                case_ids=case_ids,
                burst_count=options["burst_count"],
                guild_id=options["guild_id"],
            )
        except LiveVerifyError as exc:
            raise CommandError(str(exc)) from exc
        except User.DoesNotExist as exc:
            raise CommandError(
                f"User {options['username']!r} not found"
            ) from exc

        self.stdout.write(
            f"Live verify guild={report.guild_id} subject={report.subject}"
        )
        failed = 0
        for result in report.results:
            mark = "PASS" if result.passed else "FAIL"
            note = result.notes.splitlines()[0] if result.notes else ""
            line = f"  {result.case_id:4} {mark}  {note}"
            if result.passed:
                self.stdout.write(self.style.SUCCESS(line))
            else:
                failed += 1
                self.stderr.write(self.style.ERROR(line))
                if result.notes:
                    self.stderr.write(result.notes)

        total = len(report.results)
        summary = f"{total - failed}/{total} passed"
        if failed:
            self.stderr.write(self.style.ERROR(summary))
            raise CommandError(f"Live Discord verification failed ({summary})")
        self.stdout.write(self.style.SUCCESS(summary))
