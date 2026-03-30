# Supergateway + Docker CLI so stdio MCP images can be spawned (see docker-compose-mcp.yml).
FROM supercorp/supergateway:latest
USER root
RUN apk add --no-cache docker-cli curl
