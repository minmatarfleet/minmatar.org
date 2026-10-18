# Documentation index

Every document under `docs/`, with its status. **Current** describes the code on `main` and is kept up to date. **Historical** records a plan or a removed system; it is kept for its reasoning, and the code wins where they disagree. `backend/app/tests/test_docs.py` fails when a file under `docs/` is missing from this index, and checks the repo paths and `manage.py` commands that current docs mention.

When a plan ships, change its status here to historical and give it a header saying what shipped and what changed (see `docs/archive/plans/` for examples).

Other entry points: the [root README](../README.md) (local setup, quickstart), [backend/README.md](../backend/README.md), [frontend/app/README.md](../frontend/app/README.md), [desktop/README.md](../desktop/README.md), [mobile/README.md](../mobile/README.md), [mcps/README.md](../mcps/README.md), [backend/campaigns/README.md](../backend/campaigns/README.md). Agent rules live in `.claude/rules/` (the source of truth; `.cursor/` is generated from it by `scripts/sync_agent_config.py`).

## Development setup

| Document | Status | About |
| --- | --- | --- |
| [developer_discord_setup.md](developer_discord_setup.md) | current | Discord application and test server for local development |
| [developer_data_seeding.md](developer_data_seeding.md) | current | Seeding a dev database: users, roles, pilot features, reference data |
| [runtime-profiles.md](runtime-profiles.md) | current | How the app runs locally vs in production |

## Architecture and conventions

| Document | Status | About |
| --- | --- | --- |
| [frontend-design.md](frontend-design.md) | current | Frontend source of truth: htmx/Alpine split, tokens, compositions, components |
| [frontend-sde.md](frontend-sde.md) | current | The frontend's local SDE SQLite snapshot: where it lives, the pinned build, upgrading it |
| [architecture/feed-and-rollups.md](architecture/feed-and-rollups.md) | current | Killmail feed: ingest, monitored systems, rollups and their readers |
| [architecture/cached-aggregates.md](architecture/cached-aggregates.md) | current | Heavy aggregates: computed by Celery, read from the cache (`CachedRollup`), Redis-tolerant |
| [market-pricing.md](market-pricing.md) | current | Which market price source to use where |
| [industry/lp-buyback.md](industry/lp-buyback.md) | current | LP buyback orders: tiers, states, timers, Discord threads |
| [fleet-ships-and-refits.md](fleet-ships-and-refits.md) | current | Fleet ship lists, refits and in-game fittings |
| [tribes/tribe-publishing.md](tribes/tribe-publishing.md) | current | Tribe groups publishing posts, fleets and Discord events: rules, data, permissions, API |
| [page-progress/architecture.md](page-progress/architecture.md) | current | Page progress tracking: data model and API |
| [page-progress/frontend.md](page-progress/frontend.md) | current | Wiring page progress into a page |
| [notifications/README.md](notifications/README.md) | current | The notifications system |
| [notifications/adding-a-notification.md](notifications/adding-a-notification.md) | current | Adding a notification type |
| [notifications/industry-orders.md](notifications/industry-orders.md) | current | Industry order notifications |

## Auth

| Document | Status | About |
| --- | --- | --- |
| [auth/README.md](auth/README.md) | current | Overview of authentication and authorization |
| [auth/authentication.md](auth/authentication.md) | current | Login, JWTs, Discord identity |
| [auth/authorization.md](auth/authorization.md) | current | PilotFeature evaluation |
| [auth/feature-catalog.md](auth/feature-catalog.md) | current | Every feature code, its scope and default wiring |
| [auth/frontend-feature-gating.md](auth/frontend-feature-gating.md) | current | Frontend gates and how they map to features |
| [auth/migration.md](auth/migration.md) | current | Retiring legacy permissions |
| [auth/discord-groups.md](auth/discord-groups.md) | current | Discord roles and auth group membership |
| [auth/discord-groups-verification.md](auth/discord-groups-verification.md) | current | Live Discord sync verification playbook |

## Desktop app

| Document | Status | About |
| --- | --- | --- |
| [desktop/ccp-third-party-guidelines.md](desktop/ccp-third-party-guidelines.md) | current | CCP third-party rules every desktop feature must pass |
| [desktop/overlay-technology.md](desktop/overlay-technology.md) | current | Why the overlay is built the way it is |

## Historical

| Document | Status | About |
| --- | --- | --- |
| [campaigns/fw-campaigns-plan.md](campaigns/fw-campaigns-plan.md) | historical | Original FW campaigns plan (built in #2787); current behaviour is in `backend/campaigns/README.md` |
| [mumble-architecture.md](mumble-architecture.md) | historical | The removed Mumble voice stack |
| [archive/plans/pilotfeature_authorization_1115fb1f.plan.md](archive/plans/pilotfeature_authorization_1115fb1f.plan.md) | historical | PilotFeature authorization plan (shipped in #2430) |
| [archive/plans/planetary_interaction_alliance_feature_85238dfb.plan.md](archive/plans/planetary_interaction_alliance_feature_85238dfb.plan.md) | historical | Planetary interaction plan (shipped in #2021) |
| [archive/plans/tribes_app_overhaul_1199c279.plan.md](archive/plans/tribes_app_overhaul_1199c279.plan.md) | historical | Tribes app plan (shipped in #1977) |
| [archive/runbooks/supply-tribe-merge.md](archive/runbooks/supply-tribe-merge.md) | historical | One-off Industry + Market → Supply tribe merge runbook |

Working notes under docs/research are not indexed.
