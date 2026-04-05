#!/usr/bin/env bash
set -euo pipefail
MCP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${MCP_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "run-discord-mcp.sh: missing ${ENV_FILE}" >&2
  exit 1
fi
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    DISCORD_TOKEN|DISCORD_GUILD_ID)
      export "${key}"="${value}"
      ;;
  esac
done < "${ENV_FILE}"
if [[ -z "${DISCORD_TOKEN:-}" ]]; then
  echo "run-discord-mcp.sh: DISCORD_TOKEN missing from ${ENV_FILE}" >&2
  exit 1
fi
exec java -jar "${MCP_DIR}/discord-mcp-1.0.0.jar"
