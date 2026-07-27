"""GET /me — authenticated user's persona, progress, and awards."""

from authentication import AuthBearer
from learning.helpers import completed_learning_slugs
from learning.models import UserCertificateAward, UserLearningPreference
from learning.schemas import MeResponse
from learning.serialization import serialize_award

PATH = "me"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Learning Center progress for the authenticated user.",
    "auth": AuthBearer(),
    "response": {200: MeResponse},
}


def get_me(request):
    pref = UserLearningPreference.objects.filter(user=request.user).first()
    awards = (
        UserCertificateAward.objects.filter(user=request.user)
        .select_related("certificate")
        .order_by("awarded_at")
    )
    return MeResponse(
        persona=pref.persona if pref else None,
        persona_confirmed=bool(pref and pref.persona_confirmed_at),
        completed_learning_slugs=completed_learning_slugs(request.user),
        awards=[serialize_award(a) for a in awards],
    )
