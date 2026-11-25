"""The MCP endpoints agents (Claude) use to reach Discord and ESI.

`POST /api/agent/discord/mcp` and `POST /api/agent/esi/mcp`, with
`Authorization: Bearer <agent key>`. A missing or bad key gets a 404, so the
endpoints aren't discoverable; so does a key without ESI access on the ESI
endpoint. Browser requests (any `Origin` header) are refused.
"""

import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import keys, mcp
from .esi_tools import ESI
from .models import AgentDiscordSettings, AgentEsiSettings

MAX_BODY_BYTES = 64 * 1024


def _not_found() -> HttpResponse:
    return HttpResponse(status=404)


def _serve(request, server: mcp.Server, enabled, allowed=None):
    if request.headers.get("Origin"):
        return HttpResponse(status=403)
    key = keys.authenticate(request)
    if key is None or (allowed is not None and not allowed(key)):
        return _not_found()
    if not enabled():
        return JsonResponse(
            {"detail": "Agent access is switched off"}, status=403
        )
    if request.method != "POST":
        # No server-sent event stream and no sessions to delete.
        response = HttpResponse(status=405)
        response["Allow"] = "POST"
        return response
    if len(request.body) > MAX_BODY_BYTES:
        return HttpResponse(status=413)

    try:
        payload = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            mcp.error_reply(None, mcp.PARSE_ERROR, "Invalid JSON"), status=400
        )

    meta = {
        "ip": keys.client_ip(request),
        "user_agent": request.headers.get("User-Agent", ""),
    }
    if isinstance(payload, list):
        replies = [
            r for r in (mcp.handle(m, key, meta, server) for m in payload) if r
        ]
        if not replies:
            return HttpResponse(status=202)
        return JsonResponse(replies, safe=False)
    reply = mcp.handle(payload, key, meta, server)
    if reply is None:
        return HttpResponse(status=202)
    return JsonResponse(reply)


@csrf_exempt
def mcp_endpoint(request):
    return _serve(
        request, mcp.DISCORD, lambda: AgentDiscordSettings.get().enabled
    )


@csrf_exempt
def esi_mcp_endpoint(request):
    return _serve(
        request,
        ESI,
        lambda: AgentEsiSettings.get().enabled,
        allowed=lambda key: key.can_use_esi,
    )
