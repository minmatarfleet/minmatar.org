"""Grant, revoke or list the bot's service-account permission."""

from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandError

from authentication import (
    SERVICE_ACCOUNT_APP_LABEL,
    SERVICE_ACCOUNT_CODENAME,
    SERVICE_ACCOUNT_PERMISSION,
)


def service_account_permission() -> Permission:
    try:
        return Permission.objects.get(
            content_type__app_label=SERVICE_ACCOUNT_APP_LABEL,
            codename=SERVICE_ACCOUNT_CODENAME,
        )
    except Permission.DoesNotExist as e:
        raise CommandError(
            f"{SERVICE_ACCOUNT_PERMISSION} does not exist yet: run migrate."
        ) from e


class Command(BaseCommand):
    help = (
        "Mark the user the Discord bot's API token belongs to as the "
        f"service account ({SERVICE_ACCOUNT_PERMISSION}). Bot-only "
        "endpoints accept that user; staff are still accepted (and "
        "logged) until the staff fallback is removed."
    )

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--grant", type=int, metavar="USER_ID")
        action.add_argument("--revoke", type=int, metavar="USER_ID")
        action.add_argument("--list", action="store_true")

    def handle(self, *args, **options):
        permission = service_account_permission()

        if options["list"]:
            holders = User.objects.filter(
                user_permissions=permission
            ).order_by("id")
            if not holders:
                self.stdout.write("No user holds the service account.")
            for user in holders:
                self.stdout.write(f"{user.id}\t{user.username}")
            return

        user_id = options["grant"] or options["revoke"]
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as e:
            raise CommandError(f"No user with id {user_id}.") from e

        if options["grant"]:
            user.user_permissions.add(permission)
            verb = "Granted"
        else:
            user.user_permissions.remove(permission)
            verb = "Revoked"
        self.stdout.write(
            f"{verb} {SERVICE_ACCOUNT_PERMISSION} for user {user.id}."
        )
