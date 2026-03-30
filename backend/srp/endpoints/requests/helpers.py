from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

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


def can_view_request(
    user: User, reimbursement: EveFleetShipReimbursement
) -> bool:
    """Same rule as legacy list: owner or staff with change permission."""
    return can_update(user, reimbursement)


def visible_reimbursements_qs(
    user: User,
    *,
    fleet_id: int | None = None,
    status: str | None = None,
    user_id: int | None = None,
) -> QuerySet[EveFleetShipReimbursement]:
    qs = EveFleetShipReimbursement.objects.all()
    if status:
        qs = qs.filter(status=status)
    if fleet_id is not None:
        qs = qs.filter(fleet_id=fleet_id)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if user.has_perm("srp.change_evefleetshipreimbursement"):
        return qs
    return qs.filter(Q(user_id=user.id))


def reimbursement_to_response(r: EveFleetShipReimbursement) -> dict:
    return {
        "id": r.id,
        "fleet_id": r.fleet_id,
        "external_killmail_link": r.external_killmail_link,
        "status": r.status,
        "character_id": r.character_id,
        "character_name": r.character_name,
        "primary_character_id": r.primary_character_id,
        "primary_character_name": r.primary_character_name,
        "ship_type_id": r.ship_type_id,
        "ship_name": r.ship_name,
        "killmail_id": r.killmail_id,
        "amount": r.amount,
        "is_corp_ship": r.is_corp_ship,
        "corp_id": r.corp_id,
        "category": r.category,
        "comments": r.comments,
        "combat_log_id": (r.combat_log.id if r.combat_log else None),
    }
