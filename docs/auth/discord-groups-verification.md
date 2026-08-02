# Live Discord verification (local + test guild)

OPSEC playbook for fail-closed Discord ↔ Django ↔ affiliation ↔ tribe ↔ corp sync against the **real test Discord guild**, not mocks.

Contract: [discord-groups.md](discord-groups.md).

**Never run this against the production guild. Never commit bot tokens or OAuth secrets.**

## Goal

Confirm:

1. Discord roles always match intended privileges.
2. Django cannot gain or drop a group unless the Discord role mutate succeeded.
3. Affiliation / community / tribe / corp sources cannot stick ahead of Discord without rollback or retry.
4. Rate limits, 403 permission failures, and unknown-member (`10007`) cases behave correctly under live API conditions.

**Pass rule (every case):** Discord member roles, Django `user.groups`, and `DiscordRole.members` agree with the intended source state. Any mismatch = **FAIL / OPSEC**.

## How to run (preferred)

From `backend/`, with local settings pointed at the **test** guild:

```bash
pipenv run python manage.py verify_discord_groups \
  --username bearthatcares \
  --guild-id 1459994254427291781 \
  --i-understand-this-hits-live-discord
```

If `DISCORD_GUILD_ID` in `.env` still points at production, **`--guild-id` is required** (production is always refused). The bot token must belong to a bot that is a member of the test guild.

Optional:

| Flag | Purpose |
|------|---------|
| `--guild-id 1459994254427291781` | Override `.env` / settings guild for this run |
| `--cases A1,A2,B1` | Run a subset of the matrix |
| `--burst-count 10` | Fewer roles for F1/F2 |
| `--allow-guild-id <id>` | Allow an extra non-production test guild |

Safety gates in code (`discord/live_verify.py`):

- Production guild ID `1041384161505722368` is **always refused**.
- Default allowlist is the Minmatar Fleet Test Server (`1459994254427291781`).
- The subject username is **never** offboarded (G1 uses `verify-*` throwaways only).
- Scratch auth groups / Discord roles use the `VERIFY-` prefix and are deleted on cleanup.

## Opt-in TestCase

Skipped in normal CI / `settings_test` runs unless explicitly enabled. Uses `SimpleTestCase` (no DB transaction rollback that would diverge from Discord).

```bash
RUN_DISCORD_LIVE_VERIFY=1 \
DISCORD_LIVE_VERIFY_USER=bearthatcares \
DISCORD_LIVE_VERIFY_GUILD_ID=1459994254427291781 \
pipenv run python manage.py test discord.test_live_discord_groups_verify \
  --settings=app.settings
```

Do **not** use `--settings=app.settings_test` — that database has no linked Discord users. Set `DISCORD_LIVE_VERIFY_GUILD_ID` when `.env` still has the production guild.

## Preconditions

- Local backend with `DISCORD_BOT_TOKEN` for a bot that is **in the test guild** and can manage roles below its highest role.
- Subject user is in the test guild and has a `DiscordUser` row (e.g. `bearthatcares`).
- Affiliation types `Alliance` / `Guest` and community groups `On Leave` / `Trial` exist.
- Subject has a primary EVE character with a `corporation_id` (for corp sync cases).

### Inducing failures (what the runner does)

| Failure | Mechanism |
|---------|-----------|
| 403 / Missing Permissions | Temporarily point a `VERIFY-*` (or Alliance) `DiscordRole.role_id` at a **managed** bot role, then add/remove |
| Unreachable Discord | Temporarily set module bot token to an invalid value |
| 10007 unknown member | Throwaway user whose `DiscordUser.id` is not a guild member |
| Discord-only orphan roles | `sync_discord_user` after community sync (A4) — community sync alone only diffs Django community groups |

## Verification matrix

### A. Happy path

| ID | Action | Expect |
|----|--------|--------|
| A1 | `groups.add(VERIFY-Role)` | Discord + Django + `DiscordRole.members` |
| A2 | `groups.remove` | Role gone both sides |
| A3 | Create `VERIFY-New` group | Discord role created; `role_id` set |
| A4 | Community sync + `sync_discord_user` | Alliance present; On Leave cleared |
| A5 | Activate VERIFY tribe membership | Tribe group role aligned |
| A6 | `sync_eve_corporation_groups` | VERIFY corp member role aligned |

### B. Fail-closed add

| ID | Setup | Expect |
|----|-------|--------|
| B1 | User with no `DiscordUser` | `DiscordRoleAssignmentError`; not in Django group |
| B2 | 403 on add | Error; not in Django |
| B3 | Invalid bot token | Error; not in Django |
| B4 | Affiliation change while Discord add fails | Affiliation **rolled back** |

### C. Fail-closed remove (OPSEC critical)

| ID | Setup | Expect |
|----|-------|--------|
| C1 | 403 on remove | Still in Django **and** Discord |
| C2 | Unreachable on remove | Both still have role |
| C3 | Tribe → inactive while remove blocked | Status stays **active**; roles kept |
| C4 | Alliance → Guest while Alliance remove blocked | Never Guest-in-Django + Alliance-on-Discord |
| C5 | Healthy remove after restore | Converges |

### D. Allowed remove exceptions

| ID | Setup | Expect |
|----|-------|--------|
| D1 | Unknown member (10007) | Django remove allowed (may offboard throwaway) |
| D2 | No `DiscordUser` row | Django remove allowed |

### E. Reconcilers

| ID | Action | Expect |
|----|--------|--------|
| E1 | Stale Alliance while affiliation Guest → `sync_user_community_groups` | Alliance stripped; Guest only |
| E2 | Inactive tribe with groups still attached → remove helper | Roles stripped |
| E3 | Primary corp changed away → corp sync | Corp role removed |

### F. Burst / rate limits

| ID | Action | Expect |
|----|--------|--------|
| F1 | Burst-add N `VERIFY-Burst-*` roles | Final Discord == Django |
| F2 | Burst-remove | Same |
| F3 | Offboard throwaway then subject add | Sync still works (scoped skip, not permanent mute) |

### G. Offboard integrity

| ID | Action | Expect |
|----|--------|--------|
| G1 | `offboard_user` on **throwaway** only | User deleted |
| G2 | Subject `groups.add` immediately after | Discord sync still works |

### H. Community transitions

| ID | Action | Expect |
|----|--------|--------|
| H1 | Active Alliance → On Leave | On Leave only on Discord + Django |
| H2 | On Leave → Active Guest | Guest only |
| H3 | Interrupt leave (403 on Alliance remove) | No On-Leave-in-Django with Alliance still on Discord |

## Execution order

1. Preconditions + **A**
2. **B** then **C**
3. **D** → **E** → **F** → **G** → **H**
4. Cleanup (automatic in the runner): delete `VERIFY-*` roles/groups; restore subject affiliation / UCS / corp

## Code map

| Piece | Path |
|-------|------|
| Runner + safety gates | `backend/discord/live_verify.py` |
| Management command | `backend/discord/management/commands/verify_discord_groups.py` |
| Opt-in TestCase | `backend/discord/test_live_discord_groups_verify.py` |

## Out of scope

- Production guild testing
- Healing historical prod drift (separate `sync_discord_user` pass)
- Replacing unit tests in `discord/tests.py` / `groups/tests/test_discord_fail_closed.py`
