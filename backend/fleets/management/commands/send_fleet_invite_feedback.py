"""Send, remind, or close the one-round fleet invite feedback form.

The Discord command can preview, remind, and close. The full send is
only this command.

    python manage.py send_fleet_invite_feedback --dry-run
    python manage.py send_fleet_invite_feedback --user BearThatCares
    python manage.py send_fleet_invite_feedback --send
    python manage.py send_fleet_invite_feedback --remind
    python manage.py send_fleet_invite_feedback --close
"""

from django.core.management.base import BaseCommand, CommandError

from fleets.helpers.invite_feedback import (
    InviteFeedbackError,
    run_action,
    send_one,
)


class Command(BaseCommand):
    help = "Preview, send, remind, or close the fleet invite feedback form."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--dry-run",
            action="store_true",
            help="Print who would be asked. Writes nothing.",
        )
        group.add_argument(
            "--send",
            action="store_true",
            help="Open the round, freeze the cohort, and send the DM.",
        )
        group.add_argument(
            "--remind",
            action="store_true",
            help="Remind pilots who have not answered, once.",
        )
        group.add_argument(
            "--close",
            action="store_true",
            help="Stop new answers.",
        )
        group.add_argument(
            "--user",
            metavar="USERNAME",
            help=(
                "Send the form to this account only. Does not open the "
                "real round."
            ),
        )

    def handle(self, *args, **options):
        if options["user"]:
            self.stdout.write(send_one(options["user"]))
            return
        if options["dry_run"]:
            action, confirm = "preview", False
        elif options["send"]:
            action, confirm = "send", True
        elif options["remind"]:
            action, confirm = "remind", True
        else:
            action, confirm = "close", True
        try:
            message = run_action(action, confirm=confirm)
        except InviteFeedbackError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(message)
