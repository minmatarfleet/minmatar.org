"""GET "/assignees" - who a leader can give a task to."""

from django.db.models import Count, Q

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EvePlayer
from manage_hub.screens import SCREENS
from taskboard.models import Task
from taskboard.queries import people
from taskboard.schemas import AssigneesResponse
from taskboard.teams import Membership, can_assign

SCREEN_LABELS = {
    screen.key: screen.key.replace("_", " ").capitalize() for screen in SCREENS
}


PATH = "/assignees"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: AssigneesResponse, 403: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "Pilots matching a name, and the teams this leader can assign",
}


def get_assignees(request, q: str = ""):
    user = request.user
    if not can_assign(user):
        return 403, ErrorResponse(detail="Only leaders give out tasks.")
    found = []
    q = q.strip()
    if len(q) >= 2:
        ids = list(
            EvePlayer.objects.filter(
                Q(primary_character__character_name__icontains=q)
                | Q(user__username__icontains=q),
                user__isnull=False,
            ).values_list("user_id", flat=True)[:10]
        )
        who = people(ids)
        found = sorted(who.values(), key=lambda person: person["name"].lower())
        open_counts = dict(
            Task.objects.filter(user_id__in=ids, status=Task.STATUS_OPEN)
            .values("user_id")
            .annotate(n=Count("id"))
            .values_list("user_id", "n")
        )
        for person in found:
            person["open_tasks"] = open_counts.get(person["user_id"], 0)
    teams = [
        {"screen": key, "label": SCREEN_LABELS.get(key, key)}
        for key in sorted(Membership(user).staff_screens)
    ]
    return 200, {"people": found, "teams": teams}
