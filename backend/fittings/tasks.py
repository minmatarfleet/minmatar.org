import logging

from django.contrib.auth import get_user_model

from app.celery import app
from fittings.helpers.notifications import (
    _send_dm,
    build_daily_reminder_message,
    notify_doctrine_change_proposed,
    notify_fitting_change_proposed,
)
from fittings.helpers.permissions import (
    can_approve_doctrine_request,
    can_approve_fitting_request,
)
from fittings.models import (
    ChangeRequestStatus,
    EveDoctrineChangeRequest,
    EveFittingChangeRequest,
)

logger = logging.getLogger(__name__)

user_model = get_user_model()


@app.task
def notify_doctrine_change_request_proposed(change_request_id: int):
    change_request = (
        EveDoctrineChangeRequest.objects.select_related(
            "doctrine", "submitted_by"
        )
        .filter(pk=change_request_id)
        .first()
    )
    if (
        not change_request
        or change_request.status != ChangeRequestStatus.PENDING
    ):
        return
    notify_doctrine_change_proposed(change_request)


@app.task
def notify_fitting_change_request_proposed(change_request_id: int):
    change_request = (
        EveFittingChangeRequest.objects.select_related(
            "fitting", "submitted_by"
        )
        .filter(pk=change_request_id)
        .first()
    )
    if (
        not change_request
        or change_request.status != ChangeRequestStatus.PENDING
    ):
        return
    notify_fitting_change_proposed(change_request)


@app.task
def send_pending_change_request_reminders():
    pending_doctrine = EveDoctrineChangeRequest.objects.filter(
        status=ChangeRequestStatus.PENDING
    )
    pending_fitting = EveFittingChangeRequest.objects.filter(
        status=ChangeRequestStatus.PENDING
    )

    for user in user_model.objects.filter(is_active=True):
        doctrine_count = sum(
            1
            for req in pending_doctrine
            if can_approve_doctrine_request(user, req.tier)
        )
        fitting_count = sum(
            1
            for req in pending_fitting
            if can_approve_fitting_request(user, req.tier)
        )
        if doctrine_count or fitting_count:
            _send_dm(
                user,
                build_daily_reminder_message(
                    user, doctrine_count, fitting_count
                ),
            )
