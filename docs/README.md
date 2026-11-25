# Documentation index

Every document under `docs/`, with its status. **Current** describes the code on `main` and is kept up to date. **Historical** records a plan or a removed system; it is kept for its reasoning, and the code wins where they disagree. `backend/app/tests/test_docs.py` fails when a file under `docs/` is missing from this index, and checks the repo paths and `manage.py` commands that current docs mention.

When a plan ships, change its status here to historical and give it a header saying what shipped and what changed (see `docs/archive/plans/` for examples).

Other entry points: the [root README](../README.md) (local setup, quickstart), [backend/README.md](../backend/README.md), [frontend/app/README.md](../frontend/app/README.md), [desktop/README.md](../desktop/README.md), [mobile/README.md](../mobile/README.md), [mcps/README.md](../mcps/README.md), [backend/campaigns/README.md](../backend/campaigns/README.md). Agent rules live in `.claude/rules/` (the source of truth; `.cursor/` is generated from it by `scripts/sync_agent_config.py`). Pull requests follow `.github/pull_request_template.md` (the issue they close or refer to, frontend and backend reviews, Rust justifications, docs), checked by `scripts/check_pull_request.py`; see `.claude/rules/pull-requests.md`. Issues use the forms in `.github/ISSUE_TEMPLATE/` and the type labels in `.github/labels.json`; significant features need a design or a person's sign-off (`scripts/check_issue.py`, `.claude/rules/issues.md`).

## Development setup

| Document | Status | About |
| --- | --- | --- |
| [developer_discord_setup.md](developer_discord_setup.md) | current | Discord application and test server for local development |
| [developer_data_seeding.md](developer_data_seeding.md) | current | Seeding a dev database: users, roles, pilot features, reference data |
| [runtime-profiles.md](runtime-profiles.md) | current | How the app runs locally vs in production |
| [agent-ci-hooks.md](agent-ci-hooks.md) | current | `scripts/ci_local.py` (the CI checks a diff needs, run locally) and the Claude/Cursor hooks that run it before a push or pull request |

## Architecture and conventions

| Document | Status | About |
| --- | --- | --- |
| [frontend-design.md](frontend-design.md) | current | Frontend source of truth: htmx/Alpine split, tokens, compositions, components |
| [frontend-sde.md](frontend-sde.md) | current | The frontend's local SDE SQLite snapshot: where it lives, the pinned build, upgrading it |
| [architecture/feed-and-rollups.md](architecture/feed-and-rollups.md) | current | Killmail feed: ingest, monitored systems, rollups and their readers |
| [intel/affiliations.md](intel/affiliations.md) | current | Intel affiliation database: blocs, pets and associates learned from kill history, review, and who reads it |
| [learning/mentors.md](learning/mentors.md) | current | Learning Center tabs and one-to-one mentor classes: matching, request life, Discord DMs, classes, metrics |
| [architecture/character-sync.md](architecture/character-sync.md) | current | Character ESI sync: per-section intervals and audiences, the paced scheduler, freshness tracking, the fanout/shadow/scheduled rollout |
| [architecture/celery-queues.md](architecture/celery-queues.md) | current | Celery queues and workers, task standards (dedupe, routing, fast lane), Sentry queue monitoring |
| [architecture/cached-aggregates.md](architecture/cached-aggregates.md) | current | Heavy aggregates: computed by Celery, read from the cache (`CachedRollup`), Redis-tolerant |
| [mumble-architecture.md](mumble-architecture.md) | current | Fleet voice on Mumble: access rules, leases, sign-in, the voice service and its Redis contract |
| [architecture/deploys.md](architecture/deploys.md) | current | Production deploys without downtime: `docker rollout`, the Traefik `edge` proxy, healthchecks, migration rules |
| [architecture/nav-click-latency-plan.md](architecture/nav-click-latency-plan.md) | current | Faster nav clicks: gates cache, parallel backend calls, Campaigns and Fleets skeletons, and what was measured |
| [market-pricing.md](market-pricing.md) | current | Which market price source to use where |
| [industry/lp-buyback.md](industry/lp-buyback.md) | current | LP buyback orders: tiers, states, timers, Discord threads |
| [industry/invention-planner.md](industry/invention-planner.md) | current | T2/T3 in the build planner: invention data, maths, root copy, costs, API and UI |
| [capabilities/capability-engine-design.md](capabilities/capability-engine-design.md) | current | Character capability engine: computed skill requirements per doctrine fitting, the fit check, readiness, accounts, SDE updates |
| [fleet-ships-and-refits.md](fleet-ships-and-refits.md) | current | Fleet ship lists, refits and in-game fittings |
| [fleets/fleet-on-alt.md](fleets/fleet-on-alt.md) | current | Running a fleet on an alt: the start finds the boss character, the main stays the FC, public pages show only the alt |
| [fleets/invite-rsvp.md](fleets/invite-rsvp.md) | current | Answering a fleet invite: I'm available / I'm not available buttons, the 10-minute sign-up link with no login, High/Medium/Low confidence |
| [fleets/mining-tracking.md](fleets/mining-tracking.md) | current | Mining fleets: Track mining, per-stint ESI ledger readings (start, every 15 minutes, end), results per pilot on the Mining tab |
| [fleets/private-fleets.md](fleets/private-fleets.md) | current | Private (invite-only) fleets: waves of Discord invites, the coordination thread, ship targets, declassifying |
| [fleets/fleet-role-training-plan.md](fleets/fleet-role-training-plan.md) | current | Fleet Roles guides: the template, simulators, certificates, Training tab links, and what is not built yet |
| [tribes/tribe-publishing.md](tribes/tribe-publishing.md) | current | Tribe groups publishing posts, fleets and Discord events: rules, data, permissions, API |
| [tribes/tribe-invitations.md](tribes/tribe-invitations.md) | current | Chiefs inviting pilots to a tribe group: Discord DM, join without review, API |
| [tribes/interim-chiefs.md](tribes/interim-chiefs.md) | current | Chiefless tribes and groups: interim chief fallback, Help wanted, volunteers the executor appoints |
| [tribes/tribe-structure.md](tribes/tribe-structure.md) | current | Creating, renaming and archiving tribes and groups, and changing chiefs, on the site: who (People Team), the API, Discord roles |
| [tasks/README.md](tasks/README.md) | current | Tasks: what waits on each pilot, team work up for grabs, projects and templates, and the rules that keep it light |
| [esi_health.md](esi_health.md) | current | ESI health: characters to re-add, director tokens, scope changes and the Discord message superusers send |
| [timezones.md](timezones.md) | current | Pilot timezones (declared and inferred from activity) and the USTZ/EUTZ/AUTZ Discord roles |
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
| [auth/agent-discord-access.md](auth/agent-discord-access.md) | current | Claude reading and posting in Discord through the backend's MCP endpoint: keys, tools, post targets, audit |
| [auth/agent-esi-access.md](auth/agent-esi-access.md) | current | Claude calling ESI as any character (or granted ones) through the backend's MCP endpoint: grants, tools, limits, audit |

## Operations

| Document | Status | About |
| --- | --- | --- |
| [operations/backups.md](operations/backups.md) | current | Database backups and point-in-time recovery: what is protected, how it works, monitoring, limits, who holds the keys |
| [operations/restore-runbook.md](operations/restore-runbook.md) | current | Step-by-step restore to an isolated instance, the dropped-table variant, Plane Postgres, validation checklist |
| [operations/restore-drill.md](operations/restore-drill.md) | current | The monthly restore drill checklist |

## Desktop app

| Document | Status | About |
| --- | --- | --- |
| [desktop/ccp-third-party-guidelines.md](desktop/ccp-third-party-guidelines.md) | current | CCP third-party rules every desktop feature must pass |
| [desktop/overlay-technology.md](desktop/overlay-technology.md) | current | Why the overlay is built the way it is |

## Historical

| Document | Status | About |
| --- | --- | --- |
| [campaigns/fw-campaigns-plan.md](campaigns/fw-campaigns-plan.md) | historical | Original FW campaigns plan (built in #2787); current behaviour is in `backend/campaigns/README.md` |
| [archive/mumble-removed-stack.md](archive/mumble-removed-stack.md) | historical | The old, removed Mumble voice stack |
| [archive/plans/pilotfeature_authorization_1115fb1f.plan.md](archive/plans/pilotfeature_authorization_1115fb1f.plan.md) | historical | PilotFeature authorization plan (shipped in #2430) |
| [archive/plans/planetary_interaction_alliance_feature_85238dfb.plan.md](archive/plans/planetary_interaction_alliance_feature_85238dfb.plan.md) | historical | Planetary interaction plan (shipped in #2021) |
| [archive/plans/tribes_app_overhaul_1199c279.plan.md](archive/plans/tribes_app_overhaul_1199c279.plan.md) | historical | Tribes app plan (shipped in #1977) |
| [archive/runbooks/supply-tribe-merge.md](archive/runbooks/supply-tribe-merge.md) | historical | One-off Industry + Market → Supply tribe merge runbook |

Working notes under docs/research are not indexed.
