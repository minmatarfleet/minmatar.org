# MCP servers (local tools)

This folder holds **Model Context Protocol** servers used with Cursor: wrapper scripts, optional Docker Compose for the catalog **Reddit** image, and tracked **JAR** binaries.

**Project-scoped config:** `.cursor/mcp.json` in the repo root wires up Composio (Google Drive), Sentry, and Discord for **this project only**. Credentials live in `mcps/.env` (gitignored). Use personal accounts/tokens so work orgs are not affected.

## Quick start

1. Copy **`mcps/.env.example`** to **`mcps/.env`** and fill in values.
2. Install **Java 21+** (Discord JAR). Node.js is optional (Composio stdio fallback only).
3. Open this repo in Cursor — project MCP servers load from **`.cursor/mcp.json`** automatically.
4. In **Settings → Tools & MCP**, connect OAuth servers (Sentry) with your **personal** accounts. Connect Google Drive in the [Composio dashboard](https://dashboard.composio.dev) under **Connect Apps**.
5. Disable duplicate entries in **`~/.cursor/mcp.json`** if you also have Sentry/Discord there globally (avoids two servers with the same tools).

Variable reference:

| Variable | Used by |
| -------- | ------- |
| `COMPOSIO_API_KEY` | Composio MCP (`.cursor/mcp.json` via `${env:…}` or `run-composio-mcp.sh`) |
| `DISCORD_TOKEN`, `DISCORD_GUILD_ID` | `run-discord-mcp.sh` |
| `REDDIT_*` | `docker-compose-mcp.yml` / `run-reddit-mcp.sh` |
| `JAVA_TOOL_OPTIONS` | `run-reddit-mcp.sh` (optional JVM flags) |

### Composio API key

Set **`COMPOSIO_API_KEY`** in **`mcps/.env`**, then either:

- **Recommended:** `source mcps/source-env.sh` and launch Cursor from that shell so `${env:COMPOSIO_API_KEY}` resolves in `.cursor/mcp.json`, or
- **Fallback:** swap the `composio` entry in `.cursor/mcp.json` to use `run-composio-mcp.sh` (stdio bridge; loads `.env` directly).

## Cursor config (`.cursor/mcp.json`)

This repo includes a project config with:

| Server | Transport | Auth |
| ------ | --------- | ---- |
| **composio** | Remote HTTP | API key in `mcps/.env` → Google Drive OAuth in Composio dashboard |
| **sentry** | Remote HTTP | OAuth (personal Sentry org at connect time) |
| **discord-mcp** | Local JAR stdio | Personal bot token in `mcps/.env` |

Global config (`~/.cursor/mcp.json`) is optional. Prefer project config here so minmatar tooling stays isolated from other workspaces.

## Google Drive (town halls)

Remote MCP via [Composio Connect](https://docs.composio.dev/docs/composio-connect) — managed OAuth, no local GCP project or WSL desktop OAuth flow.

1. Sign up at [dashboard.composio.dev](https://dashboard.composio.dev) (free tier: 20k tool calls/month).
2. **AI Clients** → select **Cursor** → copy your API key into `mcps/.env` as `COMPOSIO_API_KEY`.
3. Restart Cursor (or reload MCP).

### Auth Configs vs Cursor MCP (important)

The **Platform** dashboard (Auth Configs, Users, Toolkits) and **Composio Connect MCP** (what Cursor uses) are separate scopes:

| Where | What you did | Who it applies to |
| ----- | ------------ | ----------------- |
| **Auth Configs** → Active account | Google Drive OAuth complete | Platform user (e.g. `pg-test-…`) |
| **Cursor MCP** (`connect.composio.dev/mcp`) | Needs its own connection | MCP session user (from AI Clients API key) |

An Active connection under Auth Configs does **not** automatically appear in Cursor. To use Drive from the agent, either:

- **Option A (simplest):** When the agent returns a Composio auth link, open it in your browser and sign in with Google. This binds Drive to the MCP session.
- **Option B:** In the dashboard top-left product switcher, use **Composio For You** (personal/no-code MCP) and connect apps there.

Do **not** rely on `COMPOSIO_WAIT_FOR_CONNECTIONS` in Cursor — it blocks until OAuth completes and will hang the agent turn.

Useful for town hall docs, slides, and sheets in Drive. Composio handles token refresh; revoke access anytime in the dashboard.

**Stdio fallback** if `${env:COMPOSIO_API_KEY}` is not resolved (Cursor launched from desktop, not a terminal):

```json
"composio": {
  "command": "bash",
  "args": ["${workspaceFolder}/mcps/run-composio-mcp.sh"]
}
```

## Sentry (errors)

Hosted MCP: `https://mcp.sentry.dev/mcp` (OAuth, no token in `.env`).

1. Restart Cursor with this project open.
2. **Settings → Tools & MCP** → **Connect** on `sentry`.
3. Sign in to your **personal** Sentry organization (not work). You can revoke access anytime in Sentry account settings.

If OAuth fails in Cursor, fallback stdio config:

```json
"sentry": {
  "command": "npx",
  "args": ["-y", "mcp-remote@latest", "https://mcp.sentry.dev/mcp"]
}
```

## Discord (read messages)

- **Binary:** `discord-mcp-1.0.0.jar` (tracked in git).
- **Runner:** `run-discord-mcp.sh` loads `DISCORD_TOKEN` and `DISCORD_GUILD_ID` from `mcps/.env`.

Create a **personal/community bot** at [Discord Developer Portal](https://discord.com/developers/applications) (separate from any work bot). Enable **Message Content Intent** if you need full message bodies. Invite the bot to your server with read permissions.

Key tools: `read_messages`, `find_channel`, `list_channels`, `get_channel_info`.

## Reddit (optional)

See sections below for JAR and Docker catalog setups. Reddit is **not** in `.cursor/mcp.json` by default; add it to global config if you want it everywhere.

## Layout

| Path | Purpose |
| ---- | ------- |
| `.cursor/mcp.json` | Project MCP config (Composio, Sentry, Discord) |
| `*.jar` | MCP server binaries |
| `run-*.sh` | Load `mcps/.env` and exec server |
| `source-env.sh` | Export `.env` so `${env:COMPOSIO_API_KEY}` resolves in Cursor |
| `.env` | Local secrets (not committed) |
| `.env.example` | Template for `.env` |
| `.reddit-mcp/` | Reddit JAR OAuth config and tokens (not committed) |
| `docker-compose-mcp.yml` | Docker Reddit MCP + optional HTTP/tunnel profiles |

---

## Reddit (JAR — [wrxck/reddit-mcp](https://github.com/wrxck/reddit-mcp))

- **Binary:** `reddit-mcp-1.0.0.jar` (tracked in git).
- **Runner:** `run-reddit-mcp.sh` sets `HOME` to this directory so OAuth files live under **`mcps/.reddit-mcp/`** (gitignored), not your real home directory.

First-time setup (from `mcps/`):

```bash
java -Duser.home="$(pwd)" -jar reddit-mcp-1.0.0.jar --init
java -Duser.home="$(pwd)" -jar reddit-mcp-1.0.0.jar --auth
```

On many Linux setups Java’s `user.home` comes from `/etc/passwd`, not `$HOME`, so `-Duser.home="$(pwd)"` keeps OAuth files under **`mcps/.reddit-mcp/`** (same as `run-reddit-mcp.sh`).

## Reddit (Docker catalog image)

Optional: run the official **`mcp/reddit-mcp`** image with **`docker-compose-mcp.yml`**. Credentials are the **`REDDIT_*`** variables in **`mcps/.env`** (see `.env.example`).

From `mcps/`:

```bash
docker compose -f docker-compose-mcp.yml pull
docker compose -f docker-compose-mcp.yml run --rm -it reddit-mcp
```

HTTP gateway and Cloudflare tunnel profiles are documented in the comments at the top of `docker-compose-mcp.yml`. The gateway image is built from **`../docker/mcp-gateway.Dockerfile`**.
