# MCP servers (local tools)

This folder holds **Model Context Protocol** servers used with Cursor (and similar clients): wrapper scripts, optional Docker Compose for the catalog **Reddit** image, and tracked **JAR** binaries.

## Setup

1. Copy **`mcps/.env.example`** to **`mcps/.env`** and fill in values. Do not commit `.env` (it is gitignored).
2. Install **Java 21+** for the Discord and Reddit JARs.
3. Point your MCP client at the wrapper scripts (see below).

Variable reference:

| Variable | Used by |
| -------- | ------- |
| `DISCORD_TOKEN`, `DISCORD_GUILD_ID` | `run-discord-mcp.sh` |
| `REDDIT_*` | `docker-compose-mcp.yml` (Docker Reddit image only) |
| `JAVA_TOOL_OPTIONS` | `run-reddit-mcp.sh` (optional JVM flags) |

## Cursor (`~/.cursor/mcp.json`)

Use **`command` + `args`** with absolute paths to the scripts in this repo, for example:

```json
{
  "mcpServers": {
    "discord-mcp": {
      "command": "bash",
      "args": ["/path/to/minmatar.org/mcps/run-discord-mcp.sh"]
    },
    "reddit-mcp": {
      "command": "bash",
      "args": ["/path/to/minmatar.org/mcps/run-reddit-mcp.sh"]
    }
  }
}
```

Adjust `/path/to/minmatar.org` to your checkout. Restart Cursor after changes.

## Discord (JAR)

- **Binary:** `discord-mcp-1.0.0.jar` (tracked in git).
- **Runner:** `run-discord-mcp.sh` loads only `DISCORD_TOKEN` and `DISCORD_GUILD_ID` from `mcps/.env`.

Create a bot at [Discord Developer Portal](https://discord.com/developers/applications) and invite it with the intents your server implementation expects.

## Reddit (JAR — [wrxck/reddit-mcp](https://github.com/wrxck/reddit-mcp))

- **Binary:** `reddit-mcp-1.0.0.jar` (tracked in git).
- **Runner:** `run-reddit-mcp.sh` sets `HOME` to this directory so OAuth files live under **`mcps/.reddit-mcp/`** (gitignored), not your real home directory.

First-time setup (from `mcps/`):

```bash
java -Duser.home="$(pwd)" -jar reddit-mcp-1.0.0.jar --init
java -Duser.home="$(pwd)" -jar reddit-mcp-1.0.0.jar --auth
```

On many Linux setups Java’s `user.home` comes from `/etc/passwd`, not `$HOME`, so `-Duser.home="$(pwd)"` keeps OAuth files under **`mcps/.reddit-mcp/`** (same as `run-reddit-mcp.sh`).

Use the MCP through Cursor’s `reddit-mcp` entry after that.

## Reddit (Docker catalog image)

Optional: run the official **`mcp/reddit-mcp`** image with **`docker-compose-mcp.yml`**. Credentials are the **`REDDIT_*`** variables in **`mcps/.env`** (see `.env.example`).

From `mcps/`:

```bash
docker compose -f docker-compose-mcp.yml pull
docker compose -f docker-compose-mcp.yml run --rm -it reddit-mcp
```

HTTP gateway and Cloudflare tunnel profiles are documented in the comments at the top of `docker-compose-mcp.yml`. The gateway image is built from **`../docker/mcp-gateway.Dockerfile`**.

## Layout

| Path | Purpose |
| ---- | ------- |
| `*.jar` | MCP server binaries |
| `run-*.sh` | Load `mcps/.env` and exec the JAR |
| `.env` | Local secrets (not committed) |
| `.env.example` | Template for `.env` |
| `.reddit-mcp/` | Reddit JAR OAuth config and tokens (not committed) |
| `docker-compose-mcp.yml` | Docker Reddit MCP + optional HTTP/tunnel profiles |
