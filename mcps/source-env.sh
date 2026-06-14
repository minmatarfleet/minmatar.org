#!/usr/bin/env bash
# Export mcps/.env vars into the current shell.
# Composio in .cursor/mcp.json uses ${env:COMPOSIO_API_KEY}; start Cursor from this shell.
set -a
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
set +a
echo "Loaded MCP env from mcps/.env (COMPOSIO_API_KEY available to Cursor)."
