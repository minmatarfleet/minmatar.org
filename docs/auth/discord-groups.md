# Discord roles and auth.Group membership

**Operational invariant: Discord roles MUST be accurate.**

Ping access, channel visibility, and opsec depend on Discord — not on Django `auth.Group` rows. Django is the **follower**: membership may only change when the corresponding Discord role mutate succeeds.

## Rules for callers

Anyone who adds or removes users from `auth.Group` (tribe approval, affiliation sync, corp groups, admin, Celery tasks) must follow these rules.

### Fail-closed M2M

`user.groups.add` / `.remove` / `.clear` (and reverse `group.user_set.*`) fire [`discord.signals.user_group_changed`](../../backend/discord/signals.py).

| Operation | Discord outcome | Django membership |
|-----------|-----------------|-------------------|
| Add | Role assigned (or already held) | Allowed |
| Add | No `DiscordUser`, missing/`ensure` failed, 403, unreachable, etc. | **Aborted** — raises `DiscordRoleAssignmentError` |
| Remove | Role stripped | Allowed |
| Remove | Unreachable / 403 | **Aborted** — raises `DiscordRoleAssignmentError` (keeps Django group so Discord is not a ghost privilege) |
| Remove | Unknown member (`10007`), no `DiscordUser`, or no `DiscordRole` | Allowed (nothing left on Discord to leave behind) |

Do **not** catch and ignore `DiscordRoleAssignmentError` unless you immediately retry or roll back the source write that required the group change.

### Every membership group needs a DiscordRole

There are no intentional Django-only user membership groups. Creating an `auth.Group` runs `group_post_save` → `_ensure_discord_role_for_group`. On add, missing `DiscordRole` rows are ensured again; failure aborts the add.

### Sources must not stick ahead of Discord

Writing a **source** (tribe membership inactive, affiliation change, community status) and then failing Discord leave users with Discord privileges Django no longer intends — and some paths will not retry.

| Source | Retry / rollback |
|--------|------------------|
| Corp groups | Desired-state beat `sync_eve_corporation_groups` (~30m) |
| Tribe - Chief | Desired-state beat `sync_tribe_chief_group` |
| Tribe membership | `TribeGroupMembership.save` is `atomic()` so Discord failure rolls back status; inactive sweep also retries (~2h) |
| Affiliation / community | `UserAffiliation` / `UserCommunityStatus` saves are `atomic()`; beats `update_affiliations` + `sync_community_groups` re-run `sync_user_community_groups` |

**When adding a new group source**, pick one:

1. **Desired-state reconciler** — a periodic task that diffs source → groups and retries until Discord succeeds, or  
2. **`transaction.atomic()` around the source write** so `post_save` group sync raising `DiscordRoleAssignmentError` rolls back the source.

### Offboard

Use [`offboard_user`](../../backend/users/helpers.py) / `offboard_group`. They use a **scoped** skip flag (`disable_discord_group_sync`) so cascading M2M clears do not call Discord during delete. Never permanently `disconnect` `user_group_changed` in a long-lived worker.

## Code map

| Piece | Path |
|-------|------|
| Fail-closed signals | `backend/discord/signals.py` |
| `DiscordRoleAssignmentError` | `backend/discord/exceptions.py` |
| Offboard skip context | `backend/discord/sync_context.py` |
| Community group sync | `backend/groups/helpers/__init__.py` → `sync_user_community_groups` |
| Community reconciler | `backend/groups/tasks.py` → `sync_community_groups` |
| Corp group sync | `backend/groups/tasks.py` → `sync_eve_corporation_groups` |
| Tribe auth groups | `backend/tribes/helpers/tribe_auth_groups.py`, `backend/tribes/signals.py` |
| Live verify runner | `backend/discord/live_verify.py` |
| Live verify command | `manage.py verify_discord_groups` |

## Temporary Discord-only drift

If Discord succeeds for group A then fails for group B in the same multi-group `pre_add`, Django aborts the whole M2M op, but A may already have the Discord role. `sync_discord_user` / community-corp reconcilers remove excess tracked roles. Prefer that over Django-only membership or Discord ghosts.

## Live verification (test guild)

Manual OPSEC checklist and runner: [discord-groups-verification.md](discord-groups-verification.md).
