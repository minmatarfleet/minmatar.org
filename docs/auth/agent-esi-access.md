# Agent access to ESI

Claude (in cloud sessions, or Claude Code on a PC) calls EVE's ESI as a chosen character through an MCP endpoint
on the backend, for impromptu debugging, reporting and testing. Character tokens never leave production: the agent
holds the same **agent key** it uses for Discord (`docs/auth/agent-discord-access.md`), and the backend makes each
ESI call itself with the character's stored token, through a fixed set of tools.

A key reaches either **every character** with a stored ESI token (*ESI all characters*), or only the characters
**granted** to it one by one.

Code: `backend/agent_access/esi_tools.py`. Endpoint: `POST https://api.minmatar.org/api/agent/esi/mcp`
(`agent_access/views.py`), MCP over Streamable HTTP with JSON responses and no sessions.

## What the agent can do

| Tool | Rule |
| --- | --- |
| `list_characters` | The characters this key may use, with the scopes their stored tokens hold. `search` (part of a name, or an id) and `limit` (default 50, at most 200); `total` is how many match |
| `esi_get` | One GET on any ESI route, one page per call. With `character_id` (a character the key may use) it sends that character's token; without, the call is public |
| `esi_post` | Only the read-only public lookups: `/universe/names/`, `/universe/ids/`, `/characters/affiliation/` |

- **Which characters**: with *ESI all characters*, any character with a stored ESI token (`esi.Token`); otherwise
  only the characters granted to the key. A `/characters/{id}/` route must name the character the call runs as,
  so one character's token is never sent for another's data. Corporation routes (`/corporations/{id}/…`) work
  when the character's roles let ESI answer them.
- **Reads only.** ESI's write routes (fittings, mail, fleet invites, contacts, waypoints, UI) have no tool.
- **Blocked routes**: a route containing a line of *blocked paths* in the settings is refused. The default is
  `/mail`, so character mail is never read.
- Paths carry no version (`/characters/123/assets/`, not `/latest/…`): calls go to `esi.evetech.net` with the app's
  compatibility date (`eveonline/esi_http.py`), User-Agent and error accounting, like the site's own raw calls.
- The token used is the character's stored token with the most scopes, or with `scopes` the first that holds them.
  A suspended character (`esi_suspended`) or a token that no longer refreshes is refused; the endpoint doesn't
  change the character's state.
- Answers over 256 KB are refused: ask for one page (`page`, and read `pages` in the reply) or a narrower route.

Every tool call, allowed or refused, is a row in **Agent ESI calls** (admin): key, tool, character, method, path,
arguments, ESI status, error, IP address and user agent.

## Limits

- `calls_per_minute` (30) and `calls_per_day` (1000) per key, in **Agent ESI settings**.
- When the app-wide ESI error budget (`eveonline/esi_budget.py`) is below its floor, calls are refused, so a
  debugging session can't spend the errors the site's own syncs need. ESI errors the agent causes count against
  that budget like any other.
- Each call makes one attempt with a 10-second timeout.

## Admin (Django admin → Agent access)

- **Agent keys**: tick *can use ESI*. A key without it gets a 404 from the ESI endpoint, as if it didn't exist.
  Tick *ESI all characters* too for every character with a token.
- **Agent ESI characters**: for a key without *all characters*, one row per character it may use, with a note
  saying why and an optional expiry. Prefer an expiry for a one-off debugging grant.
- **Agent ESI settings**: `enabled` (the kill switch), the per-key call limits, and blocked paths.

On production:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key esi-all mfa_XXXXXXXX
```

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key esi-grant mfa_XXXXXXXX 2112345678 --note "Asset sync, help ticket #123" --days 7
```

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key esi-revoke mfa_XXXXXXXX 2112345678
```

`esi-all` gives a key every character (`--off` takes it back to its grants); `esi-grant` grants one character.
Both turn on *can use ESI*. `agent_key create "…" --esi-all` creates a key with every character, `--esi` one with
no grants (public routes only until one is added); `agent_key list` shows `esi-all`, `esi` or `-` per key.

## Connecting an agent

`.mcp.json` loads the endpoint as the `esi` server with the same `Authorization: Bearer ${MINMATAR_AGENT_KEY}`
header as `discord`.

- **Claude cloud sessions**: the network secret saved for the Discord endpoint (host `api.minmatar.org`, header
  `Authorization`, prefix `Bearer`) is sent to every path on that host, so the same key reaches this endpoint once
  it has ESI access. If the environment's secret is limited to the Discord path, allow `/api/agent/esi/mcp` too.
  Keep the environment personal: everyone who can start a session on it can use the key, and with *all
  characters* that is every pilot's ESI data.
- **Claude Code on a PC**: set `MINMATAR_AGENT_KEY` in the environment Claude Code starts from.

## Security

- The same key checks as the Discord endpoint: only a SHA-256 of each key is stored, a missing, unknown, revoked or
  expired key gets a 404, pilot JWTs don't work, and requests with an `Origin` header get a 403.
- Pilots authorised these tokens for the alliance's own tools. An *all characters* key reads every pilot's
  wallet, assets, contracts and location: give it only to an environment as trusted as production shell access,
  and review **Agent ESI calls**. For narrower work, grant single characters with a note and an expiry. The MCP instructions tell the agent
  that pilot data is private to the alliance.
