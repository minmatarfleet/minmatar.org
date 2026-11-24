"""The ESI tools an agent may call, and the rules around them.

The agent never holds a character's token. It names a character granted to
its key (`AgentEsiCharacter`) and an ESI route, and the backend makes the
call with that character's stored token:

- GET only, plus the three read-only public POST lookups in `POST_ROUTES`.
  ESI's write routes (fittings, mail, fleet invites, contacts, waypoints)
  are out of reach.
- A `/characters/{id}/` route must name the granted character itself.
- Routes containing a fragment in `AgentEsiSettings.blocked_paths` (mail by
  default) are refused.
- Per-key call limits, the app-wide ESI error budget (`esi_budget`), one
  page per call, and a response size cap.

Every call, allowed or refused, is a row in `AgentEsiCall`.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from django.db.models import Count
from django.utils import timezone
from esi.errors import TokenInvalidError
from esi.models import Token
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from eveonline import esi_budget
from eveonline.esi_http import ESI_HOST_URL, esi_request
from eveonline.models import EveCharacter

from .mcp import Server
from .models import AgentEsiCall, AgentEsiCharacter, AgentEsiSettings, AgentKey

logger = logging.getLogger(__name__)

ESI_INFO = {"name": "minmatar-esi", "version": "1.0.0"}
ESI_INSTRUCTIONS = (
    "EVE Online ESI through Minmatar Fleet's application, for debugging, "
    "reporting and testing. list_characters shows the characters this key "
    "may use and the scopes their tokens hold. esi_get calls one GET route "
    "(path without a version, e.g. /characters/{character_id}/assets/) with "
    "that character's token; omit character_id for public routes. One page "
    "per call: pass page and read pages in the reply. Data about pilots is "
    "private to the alliance: use it for the task at hand, don't post it."
)

MAX_PATH_LENGTH = 300
MAX_QUERY_PARAMS = 20
MAX_RESPONSE_BYTES = 256 * 1024
MAX_POST_ITEMS = 1000
TIMEOUT_SECONDS = 10
PATH_RE = re.compile(r"^/[A-Za-z0-9_\-/]*$")
VERSION_RE = re.compile(r"^/(latest|legacy|dev|v\d+)(/|$)")
CHARACTER_ROUTE_RE = re.compile(r"^/characters/(\d+)(/|$)")
# Read-only lookups ESI serves as POST. Public: no character token.
POST_ROUTES = {
    "/universe/names": "ids",
    "/universe/ids": "names",
    "/characters/affiliation": "ids",
}


class ToolRefused(Exception):
    """The agent asked for something it may not do."""


@dataclass
class Context:
    key: AgentKey
    settings: AgentEsiSettings
    character_id: int | None = None
    method: str = ""
    path: str = ""
    esi_status: int | None = None


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    required: list
    handler: Callable
    annotations: dict = field(default_factory=dict)

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required,
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": True,
                **self.annotations,
            },
        }


# --- checks --------------------------------------------------------------


def _active_grants(key: AgentKey):
    now = timezone.now()
    return AgentEsiCharacter.objects.filter(key=key).exclude(
        expires_at__lte=now
    )


def check_rate(ctx: Context) -> None:
    now = timezone.now()
    calls = AgentEsiCall.objects.filter(key=ctx.key)
    if (
        calls.filter(created_at__gte=now - timedelta(minutes=1)).count()
        >= ctx.settings.calls_per_minute
    ):
        raise ToolRefused(
            f"Call rate limit: {ctx.settings.calls_per_minute} a minute per "
            "key. Wait a minute."
        )
    if (
        calls.filter(created_at__gte=now - timedelta(days=1)).count()
        >= ctx.settings.calls_per_day
    ):
        raise ToolRefused(
            f"Call rate limit: {ctx.settings.calls_per_day} a day per key."
        )
    if esi_budget.error_budget() < esi_budget.ERROR_BUDGET_FLOOR:
        raise ToolRefused(
            "The application's ESI error budget is low; try again in a "
            "minute so the site's own syncs are not cut off."
        )


def check_path(ctx: Context, path) -> str:
    if not isinstance(path, str) or not path:
        raise ToolRefused("path is required, e.g. /status/")
    if len(path) > MAX_PATH_LENGTH:
        raise ToolRefused("path is too long")
    if "?" in path:
        raise ToolRefused("Pass query parameters in query, not in path")
    if not PATH_RE.match(path) or "//" in path:
        raise ToolRefused(
            "path must be an ESI route such as /characters/123/assets/: "
            "letters, digits, -, _ and /"
        )
    if VERSION_RE.match(path):
        raise ToolRefused(
            "Leave the version out of path (no /latest or /v1): calls use "
            "the current compatibility date"
        )
    for fragment in ctx.settings.blocked_fragments():
        if fragment in path:
            raise ToolRefused(f"Routes containing {fragment} are blocked")
    ctx.path = path
    return path


def check_character(ctx: Context, character_id) -> int | None:
    """The granted character the call runs as, or None for a public call."""
    if character_id in (None, ""):
        return None  # public; ESI answers 401 where a token is needed
    try:
        character_id = int(character_id)
    except (TypeError, ValueError) as e:
        raise ToolRefused("character_id must be a number") from e
    ctx.character_id = character_id
    if not _active_grants(ctx.key).filter(character_id=character_id).exists():
        raise ToolRefused(
            "This key has no grant for that character (see list_characters)"
        )
    match = CHARACTER_ROUTE_RE.match(ctx.path)
    if match and int(match.group(1)) != character_id:
        raise ToolRefused(
            "A /characters/{id}/ route must name the character_id it runs as"
        )
    return character_id


def access_token(character_id: int, scopes=None) -> str:
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if character and character.esi_suspended:
        raise ToolRefused(
            "This character's ESI is suspended (its token stopped working); "
            "the pilot needs to add it again"
        )
    tokens = Token.objects.filter(character_id=character_id)
    if scopes:
        tokens = tokens.require_scopes(list(scopes))
    token = (
        tokens.annotate(scope_count=Count("scopes"))
        .order_by("-scope_count", "-created")
        .first()
    )
    if token is None:
        if scopes:
            raise ToolRefused("No token for this character has those scopes")
        raise ToolRefused("No ESI token is stored for this character")
    try:
        return token.valid_access_token()
    except (InvalidGrantError, TokenInvalidError) as e:
        raise ToolRefused(
            "The character's token no longer works; the pilot needs to add "
            "it again"
        ) from e


def _query(query) -> dict:
    if query in (None, ""):
        return {}
    if not isinstance(query, dict):
        raise ToolRefused("query must be an object of parameter: value")
    if len(query) > MAX_QUERY_PARAMS:
        raise ToolRefused("Too many query parameters")
    clean = {}
    for name, value in query.items():
        if not re.match(r"^[a-z_]{1,40}$", str(name)):
            raise ToolRefused(f"Bad query parameter name {name!r}")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ToolRefused(f"query.{name} must be a string or number")
        clean[name] = value
    return clean


def _reply(ctx: Context, result) -> dict:
    """The ESI answer as tool output, or a refusal for an error."""
    ctx.esi_status = result.status
    if result.status is None:
        raise ToolRefused(f"ESI did not answer: {result.error}")
    if result.status >= 400:
        body = result.data if result.data is not None else result.text
        detail = json.dumps(body)[:200] if body else ""
        raise ToolRefused(f"ESI answered {result.status}: {detail}")
    if result.error is not None:
        raise ToolRefused("ESI answered with a body that is not JSON")
    headers = result.headers
    output = {
        "status": result.status,
        "pages": _int(headers.get("X-Pages")),
        "expires": headers.get("Expires"),
        "last_modified": headers.get("Last-Modified"),
        "data": result.data,
    }
    size = len(json.dumps(output))
    if size > MAX_RESPONSE_BYTES:
        raise ToolRefused(
            f"The answer is {size // 1024} KB, over the "
            f"{MAX_RESPONSE_BYTES // 1024} KB limit: ask for one page or a "
            "narrower route"
        )
    return output


def _int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# --- tools -----------------------------------------------------------------


def list_characters(ctx: Context, args: dict) -> dict:
    grants = list(_active_grants(ctx.key).order_by("created_at"))
    ids = [g.character_id for g in grants]
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=ids)
    }
    scopes: dict[int, set] = {cid: set() for cid in ids}
    for character_id, scope in Token.objects.filter(
        character_id__in=ids
    ).values_list("character_id", "scopes__name"):
        if scope:
            scopes[character_id].add(scope)
    rows = []
    for grant in grants:
        character = characters.get(grant.character_id)
        rows.append(
            {
                "character_id": grant.character_id,
                "character_name": (
                    character.character_name if character else None
                ),
                "corporation_id": (
                    character.corporation_id if character else None
                ),
                "alliance_id": character.alliance_id if character else None,
                "esi_suspended": (
                    character.esi_suspended if character else None
                ),
                "scopes": sorted(scopes[grant.character_id]),
                "note": grant.note,
                "grant_expires_at": (
                    grant.expires_at.isoformat() if grant.expires_at else None
                ),
            }
        )
    return {"characters": rows}


def esi_get(ctx: Context, args: dict) -> dict:
    ctx.method = "GET"
    path = check_path(ctx, args.get("path"))
    character_id = check_character(ctx, args.get("character_id"))
    params = _query(args.get("query"))
    page = args.get("page")
    if page not in (None, ""):
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ToolRefused("page must be a whole number from 1")
        params["page"] = page
    scopes = args.get("scopes") or None
    if scopes is not None and (
        not isinstance(scopes, list)
        or not all(isinstance(s, str) for s in scopes)
    ):
        raise ToolRefused("scopes must be a list of scope names")
    check_rate(ctx)
    token = access_token(character_id, scopes) if character_id else None
    return _reply(
        ctx,
        esi_request(
            "GET",
            f"{ESI_HOST_URL}{path}",
            access_token=token,
            params=params or None,
            compat=True,
            timeout=TIMEOUT_SECONDS,
        ),
    )


def esi_post(ctx: Context, args: dict) -> dict:
    ctx.method = "POST"
    path = check_path(ctx, args.get("path"))
    route = path.rstrip("/")
    if route not in POST_ROUTES:
        raise ToolRefused(
            "Only these read-only POST routes are available: "
            + ", ".join(sorted(POST_ROUTES))
        )
    body = args.get("body")
    if not isinstance(body, list) or not body:
        raise ToolRefused(
            f"body must be a non-empty list of {POST_ROUTES[route]}"
        )
    if len(body) > MAX_POST_ITEMS:
        raise ToolRefused(f"At most {MAX_POST_ITEMS} items per call")
    wanted = int if POST_ROUTES[route] == "ids" else str
    if not all(
        isinstance(item, wanted) and not isinstance(item, bool)
        for item in body
    ):
        raise ToolRefused(f"body must be a list of {POST_ROUTES[route]}")
    check_rate(ctx)
    return _reply(
        ctx,
        esi_request(
            "POST",
            f"{ESI_HOST_URL}{path}",
            json_body=body,
            compat=True,
            timeout=TIMEOUT_SECONDS,
        ),
    )


TOOLS = [
    Tool(
        name="list_characters",
        description=(
            "The characters this key may call ESI as, with the scopes their "
            "stored tokens hold."
        ),
        properties={},
        required=[],
        handler=list_characters,
    ),
    Tool(
        name="esi_get",
        description=(
            "GET one ESI route, as a granted character or publicly. Returns "
            "status, pages (X-Pages), expires, last_modified and data. A "
            "/characters/{id}/ route must name the character it runs as."
        ),
        properties={
            "path": {
                "type": "string",
                "description": (
                    "The route without a version, e.g. "
                    "/characters/2112345678/assets/ or /status/"
                ),
            },
            "character_id": {
                "type": "integer",
                "description": (
                    "A character from list_characters whose token to send. "
                    "Omit for a public route."
                ),
            },
            "query": {
                "type": "object",
                "description": 'Query parameters, e.g. {"datasource": '
                '"tranquility"}. Use page for paging.',
                "additionalProperties": {"type": ["string", "number"]},
            },
            "page": {"type": "integer", "minimum": 1},
            "scopes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Use a token that holds these scopes. Default: the "
                    "character's token with the most scopes."
                ),
            },
        },
        required=["path"],
        handler=esi_get,
    ),
    Tool(
        name="esi_post",
        description=(
            "The read-only POST lookups: /universe/names/ (ids to names), "
            "/universe/ids/ (names to ids) and /characters/affiliation/ "
            "(character ids to corporation and alliance). Public."
        ),
        properties={
            "path": {
                "type": "string",
                "enum": [f"{route}/" for route in sorted(POST_ROUTES)],
            },
            "body": {
                "type": "array",
                "items": {"type": ["integer", "string"]},
                "description": "The ids, or for /universe/ids/ the names.",
            },
        },
        required=["path", "body"],
        handler=esi_post,
    ),
]


def run(tool: Tool, args: dict, key: AgentKey, meta: dict):
    ctx = Context(key=key, settings=AgentEsiSettings.get())
    started = time.monotonic()
    output = None
    error = ""
    try:
        output = tool.handler(ctx, args)
    except ToolRefused as e:
        error = str(e)
    except Exception:  # pylint: disable=broad-except
        # unexpected: reach Sentry, answer the agent with a tool error
        logger.exception("Agent ESI tool %s failed", tool.name)
        error = "Internal error"

    AgentEsiCall.objects.create(
        key=key,
        tool=tool.name,
        character_id=ctx.character_id,
        method=ctx.method,
        path=ctx.path[:300],
        arguments=args,
        esi_status=ctx.esi_status,
        ok=not error,
        error=error[:300],
        ip=meta.get("ip"),
        user_agent=(meta.get("user_agent") or "")[:300],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return output, error


ESI = Server(
    info=ESI_INFO,
    instructions=ESI_INSTRUCTIONS,
    tools=TOOLS,
    run=run,
)
