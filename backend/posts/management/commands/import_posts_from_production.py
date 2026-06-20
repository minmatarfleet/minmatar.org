"""
Copy blog posts and tags from production_readonly into the default database.

Reads production via the read-only alias; writes only to default. Ensures
referenced auth User rows exist locally (matched by username).

Usage (from backend/, with production_readonly configured):

    pipenv run python manage.py import_posts_from_production --clear

Options:
    --clear     Delete all local posts and tags before import.
    --dry-run   Validate and report counts without writing to default.
    --source    Database alias to read from (default: production_readonly).
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from posts.models import EvePost, EveTag


class Command(BaseCommand):
    help = (
        "Import blog posts and tags from production_readonly "
        "(or another alias) into the local default database."
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
            help="Remove all local EvePost and EveTag rows before import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; only validate and print planned counts.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        local = "default"
        self._validate_aliases(source, local)

        prod_tags = list(EveTag.objects.using(source).order_by("pk"))
        prod_posts = list(
            EvePost.objects.using(source)
            .select_related("user")
            .prefetch_related("tags")
            .order_by("pk")
        )
        prod_user_ids = {post.user_id for post in prod_posts}
        prod_users = {
            user.pk: user
            for user in User.objects.using(source).filter(pk__in=prod_user_ids)
        }
        if len(prod_users) != len(prod_user_ids):
            missing = sorted(prod_user_ids - set(prod_users.keys()))
            raise CommandError(
                f"Missing production User rows for post authors: {missing}"
            )

        self.stdout.write(
            f"Source={source}: {len(prod_posts)} posts, "
            f"{len(prod_tags)} tags, {len(prod_users)} authors."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic(using=local):
            if options["clear"]:
                deleted_posts, _ = EvePost.objects.using(local).all().delete()
                deleted_tags, _ = EveTag.objects.using(local).all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared local posts ({deleted_posts} rows) "
                        f"and tags ({deleted_tags} rows)."
                    )
                )

            prod_user_pk_to_local_pk = {
                pk: self._ensure_user(prod_users[pk], local)
                for pk in prod_user_ids
            }
            prod_tag_pk_to_local_pk = {
                tag.pk: self._ensure_tag(tag, local) for tag in prod_tags
            }

            created = 0
            updated = 0
            for post in prod_posts:
                was_created = self._copy_post(
                    post,
                    local,
                    prod_user_pk_to_local_pk,
                    prod_tag_pk_to_local_pk,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported into {local}: {created} created, {updated} updated."
            )
        )

    def _validate_aliases(self, source, local):
        if source not in settings.DATABASES:
            raise CommandError(
                f'Database alias "{source}" is not configured. '
                "Set production_readonly (see app settings / DB_READONLY_*)."
            )
        if source == local:
            raise CommandError("Source and destination must differ.")

    def _ensure_user(self, prod_user, local):
        existing = (
            User.objects.using(local)
            .filter(username=prod_user.username)
            .first()
        )
        if existing:
            return existing.pk
        return (
            User.objects.using(local)
            .create(
                username=prod_user.username,
                email=prod_user.email or "",
                is_active=prod_user.is_active,
                is_staff=prod_user.is_staff,
                is_superuser=prod_user.is_superuser,
            )
            .pk
        )

    def _ensure_tag(self, prod_tag, local):
        tag, _ = EveTag.objects.using(local).get_or_create(tag=prod_tag.tag)
        return tag.pk

    def _copy_post(
        self,
        post,
        local,
        prod_user_pk_to_local_pk,
        prod_tag_pk_to_local_pk,
    ):
        local_user_id = prod_user_pk_to_local_pk[post.user_id]
        local_post, created = EvePost.objects.using(local).update_or_create(
            title=post.title,
            defaults={
                "state": post.state,
                "seo_description": post.seo_description,
                "slug": post.slug,
                "content": post.content,
                "user_id": local_user_id,
            },
        )
        EvePost.objects.using(local).filter(pk=local_post.pk).update(
            date_posted=post.date_posted
        )
        local_tag_ids = [
            prod_tag_pk_to_local_pk[tag.pk] for tag in post.tags.all()
        ]
        local_post.tags.set(local_tag_ids)
        return created
