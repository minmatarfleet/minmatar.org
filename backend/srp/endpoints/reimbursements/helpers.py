from django.contrib.auth.models import User

from srp.models import EveFleetShipReimbursement


def duplicate_kill(details) -> bool:
    return (
        EveFleetShipReimbursement.objects.filter(
            killmail_id=details.killmail_id
        )
        .exclude(status="rejected")
        .exclude(status="withdrawn")
        .exists()
    )


def can_update(user: User, reimbursement: EveFleetShipReimbursement) -> bool:
    if reimbursement.user == user:
        return True
    if user.has_perm("srp.change_evefleetshipreimbursement"):
        return True
    return False
