# Supergateway + Docker CLI for wrapping stdio MCP servers as HTTP when needed.
FROM supercorp/supergateway:latest
USER root
RUN apk add --no-cache docker-cli curl
