"""
Click tracking for the recruitment scout's replies.

Each reply gets a short code. Its Discord and my.minmatar.org links point at
my.minmatar.org/go/<code>/<target>, which records the visit here and then
redirects. The link text in the reply stays the real URL.
"""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, Min
from django.utils import timezone

from recruitment.models import ScoutOutreach, ScoutOutreachClick

# Lowercase letters and digits without look-alikes (0/o, 1/l/i).
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 6

TARGET_PATTERN = re.compile(r"^[a-z0-9-]{1,32}$")

# Link previews and scripts. A forum onebox or a Reddit/Discord unfurl
# fetches the link once when the reply is posted; that is not a pilot.
BOT_USER_AGENT = re.compile(
    r"bot|crawl|spider|slurp|preview|onebox|discourse|embed|"
    r"facebookexternalhit|whatsapp|skypeuripreview|headless|"
    r"curl|wget|python-requests|httpx|aiohttp|go-http-client|okhttp",
    re.IGNORECASE,
)


def tracked_base_url(code: str) -> str:
    return f"{settings.WEB_LINK_URL.rstrip('/')}/go/{code}/"


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def register_outreach(
    *, surface: str, thread_url: str, prospect: str, seat: str, user
) -> ScoutOutreach:
    """The thread's outreach record, created on first draft."""
    outreach = ScoutOutreach.objects.filter(thread_url=thread_url).first()
    if outreach:
        outreach.surface = surface
        outreach.prospect = prospect or outreach.prospect
        outreach.seat = seat or outreach.seat
        outreach.save(update_fields=["surface", "prospect", "seat"])
        return outreach

    for _ in range(5):
        try:
            return ScoutOutreach.objects.create(
                code=_new_code(),
                surface=surface,
                thread_url=thread_url,
                prospect=prospect,
                seat=seat,
                created_by=user,
            )
        except IntegrityError:
            # A code collision, or another request registered the thread.
            existing = ScoutOutreach.objects.filter(
                thread_url=thread_url
            ).first()
            if existing:
                return existing
    raise RuntimeError("Could not allocate a scout outreach code")


def is_bot(user_agent: str) -> bool:
    return not user_agent.strip() or bool(BOT_USER_AGENT.search(user_agent))


def hash_visitor(client_ip: str) -> str:
    """Keyed so the stored value can't be reversed by hashing every IP."""
    ip = client_ip.split(",")[0].strip()
    return hmac.new(
        settings.SECRET_KEY.encode(), ip.encode(), hashlib.sha256
    ).hexdigest()


def record_click(
    *, code: str, target: str, client_ip: str, user_agent: str
) -> ScoutOutreachClick | None:
    """None when the code is unknown or the target isn't a slug."""
    if not TARGET_PATTERN.match(target):
        return None
    outreach = ScoutOutreach.objects.filter(code=code.lower()).first()
    if outreach is None:
        return None
    return ScoutOutreachClick.objects.create(
        outreach=outreach,
        target=target,
        visitor=hash_visitor(client_ip),
        user_agent=user_agent[:255],
        is_bot=is_bot(user_agent),
    )


def outreach_stats(days: int) -> list[dict]:
    """Replies registered in the last `days`, newest first, with clicks."""
    since = timezone.now() - timedelta(days=days)
    outreach = list(
        ScoutOutreach.objects.filter(created_at__gte=since).order_by(
            "-created_at"
        )
    )
    human = ScoutOutreachClick.objects.filter(
        outreach__in=outreach, is_bot=False
    )
    by_target = {}
    for row in human.values("outreach_id", "target").annotate(
        visitors=Count("visitor", distinct=True)
    ):
        by_target.setdefault(row["outreach_id"], {})[row["target"]] = row[
            "visitors"
        ]
    totals = {
        row["outreach_id"]: row
        for row in human.values("outreach_id").annotate(
            visitors=Count("visitor", distinct=True),
            first_click_at=Min("created_at"),
        )
    }

    stats = []
    for item in outreach:
        total = totals.get(item.id, {})
        stats.append(
            {
                "code": item.code,
                "surface": item.surface,
                "thread_url": item.thread_url,
                "prospect": item.prospect,
                "seat": item.seat,
                "created_at": item.created_at,
                "link_base": tracked_base_url(item.code),
                "visitors": total.get("visitors", 0),
                "first_click_at": total.get("first_click_at"),
                "clicks": by_target.get(item.id, {}),
            }
        )
    return stats
