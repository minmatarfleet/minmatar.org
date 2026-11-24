# Agent access to Discord

Claude (in cloud sessions, or Claude Code on a PC) reads and posts in the Discord servers the bot is in through
an MCP endpoint on the backend. The bot token never leaves production: the agent holds an **agent key** that
works only on this endpoint, and the backend makes each Discord call itself, through a fixed set of tools.

Code: `backend/agent_access/`. Endpoint: `POST https://api.minmatar.org/api/agent/discord/mcp`
(`agent_access/views.py`), MCP over Streamable HTTP with JSON responses and no sessions.

## What the agent can do

| Tools | Rule |
| --- | --- |
| `list_servers`, `list_channels`, `get_channel_info`, `list_active_threads`, `list_archived_threads`, `read_messages`, `get_message`, `get_attachment`, `search_members`, `get_member`, `list_roles` | Reads, on every server the bot is in, except blocked servers and channels |
| `send_message`, `add_reaction` | Writes: only in a channel with a post target or a #help ticket thread, with a key that may write, within the rate limits |
| `close_help_ticket` | A write, under the same rules, for #help ticket threads only: posts a closing notice with the reason, archives and locks the thread, and marks its `HelpTicket` closed (like the ticket's Close button) |

#help ticket threads are postable without a post target: the threads under `DISCORD_HELP_CHANNEL_ID` (backend
env, the same variable the bot uses to open tickets; default the Minmatar Fleet #help channel). #help itself,
where the ticket panel lives, is not. A read block on #help or its category still blocks them, and
`writes_enabled` still switches them off. A ticket the agent closes records the key's name in its close reason and
the key's creator as *closed by*.

There are no tools for bans, kicks, roles, channel permissions, webhooks, invites, edits or deletes, so the bot's
other rights (Administrator on some servers) are out of the agent's reach. `send_message` never pings
`@everyone`, `@here` or roles; it pings only the users passed in `mention_user_ids`. DMs are not available.

Every tool call, allowed or refused, is a row in **Agent Discord calls** (admin): key, tool, server, channel,
arguments, result, IP address and user agent.

## Admin (Django admin → Agent access)

- **Agent keys**: add one to create a key (it is shown once, in the page message), or use the command below.
  Revoke with the list action. A key can be read-only and can expire.
- **Agent Discord post targets**: where writes are allowed. A row with only a server id allows every channel
  there; with a channel id, that channel (and its threads, unless *include threads* is off). No rows: no writes
  anywhere.
- **Agent Discord read blocks**: servers or channels the agent may not read or post in. A category or channel
  also blocks the threads under it.
- **Agent Discord settings**: `enabled` (off: every request is refused, the kill switch), `writes_enabled`,
  and the per-key limits `writes_per_minute` and `writes_per_day`.

On production:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key create "Claude cloud: Production"
```

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key list
```

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py agent_key revoke mfa_XXXXXXXX
```

Use one key per place it is used (each cloud environment, each PC), so one can be revoked alone and the audit log
says which was used.

## Connecting an agent

`.mcp.json` loads the endpoint as the `discord` server, sending
`Authorization: Bearer ${MINMATAR_AGENT_KEY}`. `.claude/settings.json` makes `send_message`, `add_reaction` and
`close_help_ticket` ask for approval every time.

- **Claude cloud sessions**: save the key as a **network secret** on the cloud environment, for host
  `api.minmatar.org`, header `Authorization`, prefix `Bearer`. The session's proxy adds it to requests to
  that host, so the key is never in the container. Keep the environment personal: everyone who can start a
  session on it can use the key. A new session loads the server.
- **Claude Code on a PC**: set `MINMATAR_AGENT_KEY` in the environment Claude Code starts from.
- **Cursor** still uses the older stdio jar (`mcps/run-discord-mcp.sh`, see `mcps/README.md`).

## Security

- Only a SHA-256 of each key is stored. A missing, unknown, revoked or expired key gets a 404, the same as a
  path that doesn't exist. Pilot JWTs don't work here.
- Requests with an `Origin` header (browsers) get a 403.
- A refused request that carries a key-shaped token (`mfa_…`) is logged as an error (Sentry), once an hour per
  address, and so is a key hitting its write limit. Bare scans without a key are not alerted.
- Discord calls make one attempt with an 8-second timeout. A Discord rate limit is returned to the agent with
  its Retry-After rather than retried inside the web request.
- Message contents are written by other people. The server's MCP instructions tell the agent to treat them
  as data, not instructions; post targets and approval prompts are what bound the damage if it doesn't.
