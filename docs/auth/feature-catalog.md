# Feature catalog

Reference for every feature in `backend/groups/features/registry.py`. The registry is the source of truth — if this table drifts, trust the code. Default wiring is seeded only when a feature's M2M sets are empty; live wiring may differ (check Django admin → Pilot features).

Unless noted, features deny community status `on_leave` on the scope path. The optional `legacy_permission` column is the Django permission used as a fallback by `can_use_feature`.

## Tribes

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `tribes.apply` | `tribe_group_target` | `tribes.add_tribegroupmembership` | Alliance, Associate |
| `tribes.manage_memberships` | `tribe_chief` | `tribes.change_tribegroupmembership` | — (chiefs) |

## Fleets

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `fleets.view` | `resource_match` | `fleets.view_evefleet` | Alliance, Militia, Associate |
| `fleets.create` | `affiliation` | `fleets.add_evefleet` | Alliance |
| `fleets.delete` | `staff` | `fleets.delete_evefleet` | staff permission |

## SRP

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `srp.view` | `affiliation` | `srp.view_evefleetshipreimbursement` | Alliance, Militia |
| `srp.submit` | `resource_match` | — | Alliance |
| `srp.resolve` | `staff` | `srp.add_evefleetshipreimbursement` | staff permission |
| `srp.process` | `staff` | `srp.change_evefleetshipreimbursement` | staff permission |

## Structures and moons

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `structures.view` | `affiliation` | `structures.view_evestructure` | Alliance, Associate |
| `structures.timers.view` | `affiliation` | `structures.view_evestructuretimer` | Alliance, Associate |
| `structures.timers.manage` | `affiliation` | `structures.add_evestructuretimer` | Alliance |
| `moons.view` | `affiliation` | `moons.view_evemoon` | Alliance |
| `moons.manage` | `staff` | `moons.add_evemoon` | staff permission |

## Services and content

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `mumble.access` | `affiliation` | `mumble.view_mumbleaccess` | Alliance, Associate |
| `posts.create` | `affiliation` | `posts.add_evepost` | Alliance |
| `posts.edit` | `affiliation` | `posts.change_evepost` | Alliance (author check in endpoint) |
| `posts.delete` | `affiliation` | `posts.delete_evepost` | Alliance (author check in endpoint) |

## Industry

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `industry.mining.view` | `affiliation` | `industry.view_miningupgradecompletion` | Alliance |
| `industry.mining.submit` | `affiliation` | `industry.add_miningupgradecompletion` | Alliance |
| `industry.order.submit` | `tribe_chief` | — | Industry tribe groups (`industry.subcapital-production`, `industry.capital-production`, `industry.mining`, `industry.planetary-interaction`) |

## Staff / administration

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `applications.view` | `staff` | `applications.view_evecorporationapplication` | staff permission |
| `applications.manage` | `staff` | `applications.change_evecorporationapplication` | staff permission |
| `characters.view_staff` | `staff` | `eveonline.view_evecharacter` | staff permission |
| `characters.delete_staff` | `staff` | `eveonline.delete_evecharacter` | staff permission |
| `fittings.doctrine.approve` | `staff` | — | staff permission |
| `fittings.doctrine.propose` | `staff` | — | staff permission |
| `tech.ops` | `auth_group` | — | Technology Team auth group (no `on_leave` deny) |
