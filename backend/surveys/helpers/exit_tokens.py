"""The no-login exit survey link (#3198, design 07).

A signed token for one invite, valid 30 days, answerable once. A bad token
and a used or expired one are told apart only so the page can say "used or
expired" without naming the survey or the corporation.
"""

from datetime import timedelta

from django.core import signing
from django.utils import timezone

from app.links import site_url
from surveys.models import ExitSurveyInvite

SALT = "surveys.exit"
MAX_AGE = timedelta(days=30)


class TokenInvalid(Exception):
    """Not a token we issued."""


class TokenGone(Exception):
    """Used, or older than 30 days."""


def mint(invite: ExitSurveyInvite) -> str:
    return signing.dumps({"i": invite.pk}, salt=SALT, compress=True)


def survey_url(token: str) -> str:
    return site_url(f"/exit-survey/{token}/")


def invite_for(token: str) -> ExitSurveyInvite:
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired as exc:
        raise TokenGone() from exc
    except signing.BadSignature as exc:
        raise TokenInvalid() from exc
    invite = (
        ExitSurveyInvite.objects.select_related("departure__corporation")
        .filter(pk=data.get("i"))
        .first()
    )
    if invite is None:
        raise TokenInvalid()
    if invite.responded_at is not None or invite.expires_at <= timezone.now():
        raise TokenGone()
    return invite
