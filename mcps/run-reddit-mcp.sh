#!/usr/bin/env bash
set -euo pipefail
MCP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${MCP_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "run-reddit-mcp.sh: missing ${ENV_FILE}" >&2
  exit 1
fi
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    JAVA_TOOL_OPTIONS)
      export "${key}"="${value}"
      ;;
  esac
done < "${ENV_FILE}"
# wrxck/reddit-mcp stores OAuth under user.home/.reddit-mcp. Java often ignores $HOME and uses
# /etc/passwd for user.home, so force both for Cursor/subprocess environments.
exec env HOME="${MCP_DIR}" java "-Duser.home=${MCP_DIR}" -jar "${MCP_DIR}/reddit-mcp-1.0.0.jar"
