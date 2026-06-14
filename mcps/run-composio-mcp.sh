#!/usr/bin/env bash
# Composio MCP stdio bridge (loads API key from mcps/.env).
# Use when ${env:COMPOSIO_API_KEY} interpolation in .cursor/mcp.json fails
# (common when Cursor is not launched from a shell that sourced mcps/.env).
set -euo pipefail

MCP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${MCP_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "run-composio-mcp.sh: missing ${ENV_FILE}" >&2
  exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    COMPOSIO_API_KEY)
      export "${key}"="${value}"
      ;;
  esac
done < "${ENV_FILE}"

if [[ -z "${COMPOSIO_API_KEY:-}" ]]; then
  echo "run-composio-mcp.sh: COMPOSIO_API_KEY missing from ${ENV_FILE}" >&2
  exit 1
fi

exec npx -y mcp-remote@latest https://connect.composio.dev/mcp \
  --header "x-consumer-api-key: ${COMPOSIO_API_KEY}"
