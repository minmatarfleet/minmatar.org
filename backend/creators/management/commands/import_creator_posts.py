"""
Import recent Reddit / YouTube posts from linked Thinkspeak accounts as EvePosts.

Reads CreatorAccount rows from --accounts-from (default production_readonly)
and writes EvePosts to the default database. Dry-run is always safe.
Writing when DEBUG is False requires --force.

Usage (from backend/):

    pipenv run python manage.py import_creator_posts --days 30 --dry-run
    pipenv run python manage.py import_creator_posts --days 30
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from creators.models import CreatorAccount, CreatorProvider
from creators.post_import import (
    apply_imports,
    collect_candidates,
    org_reddit_token,
    partition_candidates,
)
from posts.models import EvePost


class Command(BaseCommand):
    help = (
        "Import recent linked Reddit/YouTube posts into EvePost rows "
        "for /alliance/content."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Lookback window in days (default 30).",
        )
        parser.add_argument(
            "--state",
            default="published",
            choices=["draft", "published", "trash"],
            help="EvePost state to create (default published).",
        )
        parser.add_argument(
            "--accounts-from",
            default="production_readonly",
            help="DB alias to read CreatorAccount rows from.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and classify only; do not write EvePosts.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow writing EvePosts when DEBUG is False.",
        )

    def handle(self, *args, **options):
        _load_reddit_settings_from_dotenv()
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be >= 1")
        if (
            not options["dry_run"]
            and not settings.DEBUG
            and not options["force"]
        ):
            raise CommandError(
                "Refusing to write EvePosts because DEBUG is False. "
                "Pass --force if you intended this."
            )
        source = options["accounts_from"]
        if source not in settings.DATABASES:
            raise CommandError(f'Database alias "{source}" is not configured.')

        cutoff = timezone.now() - timedelta(days=days)
        accounts = list(
            CreatorAccount.objects.using(source)
            .select_related("user")
            .filter(
                provider__in=[
                    CreatorProvider.REDDIT,
                    CreatorProvider.YOUTUBE,
                ]
            )
            .order_by("provider", "id")
        )
        if not accounts:
            raise CommandError(
                f"No Reddit/YouTube creator accounts on alias {source}."
            )

        token = org_reddit_token()
        candidates = collect_candidates(
            accounts, cutoff=cutoff, reddit_token=token
        )
        to_import, skipped = partition_candidates(
            candidates, posts=EvePost.objects.all()
        )

        self.stdout.write(
            f"Accounts={len(accounts)} cutoff={cutoff.isoformat()} "
            f"fetched={len(candidates)} import={len(to_import)} "
            f"skip={len(skipped)}"
        )
        for candidate in skipped:
            self.stdout.write(
                f"  SKIP [{candidate.skip_reason}] {candidate.provider} "
                f"{candidate.published_at.date()} {candidate.title[:70]}"
            )
        for candidate in to_import:
            self.stdout.write(
                f"  IMPORT [{candidate.suggested_tag}] {candidate.provider} "
                f"{candidate.published_at.date()} {candidate.title[:70]}"
            )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("Dry run — no posts written.")
            )
            return

        created = apply_imports(to_import, state=options["state"])
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(created)} EvePost(s).")
        )
        for post in created:
            self.stdout.write(f"  #{post.id} {post.state} {post.title}")


def _load_reddit_settings_from_dotenv() -> None:
    if settings.REDDIT_CLIENT_ID and settings.REDDIT_USERNAME:
        return
    env_path = Path(settings.BASE_DIR) / ".env"
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)
    settings.REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
    settings.REDDIT_SECRET = os.environ.get("REDDIT_SECRET", "")
    settings.REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME", "")
    settings.REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", "")
