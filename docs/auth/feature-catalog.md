# Feature catalog

Reference for every feature in `backend/groups/features/registry.py`. The registry is the source of truth. `groups/tests/test_feature_catalog_doc.py` fails when a registry code is missing here or its scope, legacy permission or `on_leave` note disagrees, so add the row in the same PR as the code. Default wiring is seeded only when a feature's M2M sets are empty; live wiring may differ (check Django admin → Pilot features).

Unless noted, features deny community status `on_leave` on the scope path. The optional `legacy_permission` column is the Django permission used as a fallback by `can_use_feature`.

## Tribes

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `tribes.apply` | `tribe_group_target` | `tribes.add_tribegroupmembership` | Alliance, Associate (overridable per `TribeGroup.allowed_affiliations`) |
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
| `posts.create` | `affiliation` | `posts.add_evepost` | Alliance |
| `posts.edit` | `affiliation` | `posts.change_evepost` | Alliance (author check in endpoint) |
| `posts.delete` | `affiliation` | `posts.delete_evepost` | Alliance (author check in endpoint) |
| `creators.connect` | `tribe_membership` | — | Thinkspeak (`pulse.thinkspeak`) |

## Industry

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `industry.order.submit` | `tribe_chief` | — | Industry tribe groups (`industry.subcapital-production`, `industry.capital-production`, `industry.mining`, `industry.planetary-interaction`) |
| `industry.order.submit.produced` | `tribe_membership` | — | Supply Market tribe group (`supply.market`); orders limited to produced catalog items |
| `industry.loyalty.trade` | `affiliation` | — | Alliance, Militia, Associate (post LP sell orders on the buyback board) |
| `industry.loyalty.manage` | `tribe_membership` | — | LP buyback tribe group (`supply.loyalty-points`): post buy orders, claim and settle |

## Campaigns

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `campaigns.view` | `affiliation` | `campaigns.view_campaign` | Alliance, Militia, Associate |
| `campaigns.enlist` | `affiliation` | `campaigns.add_campaignenlistment` | Alliance |
| `campaigns.form_gang` | `affiliation` | `campaigns.add_campaignevent` | Alliance |
| `campaigns.create` | `auth_group` | `campaigns.add_campaign` | — (no groups seeded; the legacy permission decides) |
| `campaigns.manage` | `staff` | `campaigns.change_campaign` | staff permission |

## Intel

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `intel.view` | `affiliation` | `intel.view_intelreport` | Alliance, Associate |
| `intel.report` | `affiliation` | `intel.add_intelreport` | Alliance, Associate |

## Staff / administration

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `applications.view` | `staff` | `applications.view_evecorporationapplication` | staff permission |
| `recruitment.scout` | `staff` | `recruitment.add_scoutoutreach` | staff permission (register scout replies, read click stats) |
| `applications.manage` | `staff` | `applications.change_evecorporationapplication` | staff permission |
| `characters.view_staff` | `staff` | `eveonline.view_evecharacter` | staff permission |
| `characters.delete_staff` | `staff` | `eveonline.delete_evecharacter` | staff permission |
| `fittings.doctrine.approve` | `staff` | — | staff permission |
| `fittings.doctrine.propose` | `staff` | — | staff permission |
| `tech.ops` | `auth_group` | — | Technology Team auth group (no `on_leave` deny) |
| `alliance.health` | `staff` | `alliance.view_alliancehealth` | staff permission (no `on_leave` deny) |
| `alliance.health.executor` | `auth_group` | — | People Team auth group (every corporation on the health board, change any member's community status) |
| `surveys.manage` | `staff` | `surveys.change_surveycampaign` | staff permission (no `on_leave` deny); response content stays superuser-only |

## Site gates

Added to move frontend gating off Django permission strings ([frontend-feature-gating.md](frontend-feature-gating.md)). They ship unwired, so their audience is exactly the legacy permission's; superuser-only codes use `auth_group` with no groups.

| Code | Scope | Legacy permission | Default wiring |
|------|-------|-------------------|----------------|
| `fleets.manage_any` | `staff` | `fleets.manage_any_fleet` | staff permission |
| `tribes.roster.view` | `affiliation` | `eveonline.add_evecharactertag` | — |
| `industry.industrialists.view` | `affiliation` | `eveonline.add_evecharactertag` | — |
| `characters.readiness` | `affiliation` | `eveonline.add_evecharactertag` | — |
| `corporations.members.view_all` | `staff` | `eveonline.view_evecorporation` | staff permission |
| `notifications.push` | `affiliation` | `subscriptions.add_usersubscription` | — |
| `learning.admin` | `staff` | `learning.change_certificate` (staff: `learning.view_certificate`) | staff permission |
| `skillsets.admin` | `staff` | `eveonline.change_eveskillset` (staff: `eveonline.view_eveskillset`) | staff permission |
| `content.manage` | `tribe_membership` | — | Thinkspeak (`pulse.thinkspeak`), no `on_leave` deny |
| `surveys.results.view` | `auth_group` | — | — (superusers only; no `on_leave` deny) |
| `site.debug_pages` | `auth_group` | — | — (superusers only; no `on_leave` deny) |
| `site.all_pages` | `auth_group` | — | — (superusers only; no `on_leave` deny; page finder and breadcrumbs list every page) |
| `characters.lookup` | `auth_group` | — | — (superusers only; no `on_leave` deny) |
