# Pin Node 22: node:lts floated to 24 and better-sqlite3 aborts on Statement
# teardown (Assertion failed: (env) != nullptr in RemoveEnvironmentCleanupHook).
FROM node:22-bookworm AS base
WORKDIR /app

# By copying only the package.json and package-lock.json here, we ensure that the following `-deps` steps are independent of the source code.
# Therefore, the `-deps` steps will be skipped if only the source code changes.
COPY app/package.json app/package-lock.json ./

FROM base AS prod-deps
RUN npm install --production

FROM base AS build-deps
RUN npm install --production=false

FROM build-deps as unit-tests
COPY app/ .
RUN npm run check

FROM build-deps AS build
COPY app/ .

# Sentry DSN/auth are decided at build time by @sentry/astro. Mount frontend/.env
# (compose secret) so real values override .env.BUILDONLY DUMMYs; runtime env_file
# alone cannot re-enable a build that baked enabled:false.
ENV NODE_OPTIONS=--max_old_space_size=4096
ENV NODE_ENV=production
RUN --mount=type=secret,id=frontend_env,dst=/app/.env,required=false \
    npm run prodbuild

FROM base AS runtime
COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY healthcheck.mjs ./healthcheck.mjs

ENV HOST=0.0.0.0
ENV PORT=4321
EXPOSE 4321
ENTRYPOINT ["node", "dist/server/entry.mjs"]

# Rust, the component library (Storybook), served at my.minmatar.org/rust by
# the `rust` service in docker-compose-prod.yml. Stories render real Astro
# components through Vite SSR at runtime, so this image keeps the full
# node_modules and the source the render server snapshots.
FROM build-deps AS rust-build
COPY app/ .
ENV NODE_OPTIONS=--max_old_space_size=4096
RUN npm run rust:build

FROM build-deps AS rust
COPY app/ .
COPY --from=rust-build /app/storybook-static ./storybook-static
COPY --from=rust-build /app/storybook-server ./storybook-server
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=6007
EXPOSE 6007
# exec so node gets SIGTERM; the dummy build env satisfies astro.config.mjs,
# which the render server loads.
CMD ["sh", "-c", "set -a; . ./.env.BUILDONLY; set +a; exec node rust/server.mjs"]
