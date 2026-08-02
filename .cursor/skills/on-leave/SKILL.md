---
name: on-leave
description: >-
  Assess alliance members for On Leave community status using fleet attendance,
  killmails, and Discord voice, then produce a reviewer report and admin upload
  CSV. Use when putting people on leave, reviewing inactive alliance members,
  stripping ping status for OPSEC or absence, auditing who is not participating
  in alliance fleets, or running a leave hygiene pass.
---

# On Leave

Imposed leave for Alliance members who are **not participating in alliance
fleets**. Decide leave vs keep from metrics; deliver a **report + upload CSV**.
Do not change status yourself — the executor uploads after review.

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md).

## Policy

Generally, if they're not participating in alliance fleets, we put them on leave.

- **Away:** takes away ping status so they're not getting constant pings and feel
  the guilt of logging in.
- **OPSEC:** for people in alliance but not participating, removes ping status;
  they have to talk to a CEO to restore it.

Tag every recommend **Away** or **OPSEC**. Same `on_leave` status either way.

`on_leave` → Django **On Leave** group only (affiliation role stripped) via
`sync_user_community_groups`. Most PilotFeatures deny `on_leave`.

Imposed leave only — do not invent declared LOA requests.

## Quick start

```bash
cd backend
pipenv run python ../.cursor/skills/on-leave/scripts/fetch_alliance_activity.py --json --max-fleets 6
```

Defaults: **90d** window; soft line **~1 fleet/month** (≈ **3 fleets / 90d**).
Override only from session context (quiet war window, user-named exempts).

## Workflow

```
Task Progress:
- [ ] Fetch (--max-fleets 6)
- [ ] Drop auto-exempts (staff, directors) + rejoin/restore grace + named exempts
- [ ] Decide leave/keep; Story + Conf + reason
- [ ] Emit report + CSV
- [ ] Stop for executor review/upload
```

## Scope

| Filter | Value |
|--------|--------|
| Affiliation | `Alliance` (check prod name if fetch is empty) |
| Status | `active` only (`previous_status` from fetch) |
| Activity | All linked `EveCharacter`s (account-level) |

**Auto-exempt** (omit from recommend):

- Auth groups: `People Team`, `Technology Team`, `Tribe - Chief`
- Corporation directors: any `Corp … Director` / `Corporation Director` auth
  group, or user on `EveCorporation.directors`
- Named CEOs / LTI this session

**Recent rejoin grace** (omit from recommend): first fleet in the 90d window
falls within the last **30 days**, and no fleets in the **30–180d** band before
that (returning after a long gap). Example: one fleet yesterday after months
dark → keep, do not flip.

**Recent restore grace** (omit from recommend): any
`UserCommunityStatusHistory` row in the last **30 days** with
`from_status=on_leave` → `to_status=active` (or other non-leave). Someone a CEO
just took off leave should not be flipped back on the next hygiene pass. Fetch
exposes `restored_from_leave_at` (ISO date or `null`); treat non-null as omit.

## Signals

| Signal | Model | Roll-up |
|--------|--------|---------|
| Fleets | `EveFleetInstanceMember` | Distinct instances across linked EVE IDs |
| Kills | `EveCharacterKillmailAttacker` | Attackers; exclude self-victim |
| Voice | `DiscordChannelActivityRecord` | `voice_minute` by Django `username` → hours |
| Restore | `UserCommunityStatusHistory` | Latest `on_leave`→non-leave in last 30d → `restored_from_leave_at` |

Fleets are primary. Kills/voice set Away vs OPSEC and break ties. Login,
mining, PI, industry do not clear the fleet bar unless this run expands
participation. Note untracked fleets / ESI gaps / zero linked chars in reasons
when they matter.

## Decision rules (90d)

1. Exempt / director / recent-rejoin grace / recent-restore grace → keep (omit).
2. Fleets ≥ 6 → keep (even low kills).
3. Fleets 0–2, weak support (under ~5 kills and under ~5h voice) → **recommend**.
   Away if kills≈0 and voice≈0; else OPSEC. Conf **high**.
4. Fleets 0–2, strong kills (~15+) or voice (~10h+) → **recommend** OPSEC.
   Conf **medium** if killboard-heavy (untracked ops possible).
5. Fleets 3–5 → **keep** if ~5+ kills, ~5h+ voice, or clear support pattern;
   else **recommend**, Conf **medium**.
6. No linked characters → **recommend**, Conf **medium**, caveat in reason.

Bias: leave for 0–2 fleets; keep for 3+. Quiet alliance (already stated) → treat
0–3 like 0–2. Resolve every case — no borderline dump, no per-pilot questions.

Reason line: Story + 1–2 metrics (+ caveat if needed). See [examples.md](examples.md).

## Deliverables

Always both. Sort recommends by Conf (`high` then `medium`).

**Summary:** `N recommended (H/M); K kept; E exempt. Window: 90d.`

### Report

| Username | Primary | Previous status | New status | Fleets (90d) | Kills (90d) | Voice | Story | Conf | Reason |
|----------|---------|-----------------|------------|-------------:|------------:|------:|-------|------|--------|

- Previous = fetch `previous_status` (normally `active`)
- New = `on_leave`
- Voice as hours (`12.5h`)
- Kept/exempt: counts only unless asked

### CSV (admin upload)

Recommended rows only:

```csv
username,community_status,reason
someuser,on_leave,Away — 0 fleets, 0 kills, 0h voice (90d)
otheruser,on_leave,OPSEC — 0 fleets, 2 kills, 25h voice
```

`community_status` = `on_leave`. `reason` ≤255. Username = Django username.
Previous/New are report-only.

| Flag | Use |
|------|-----|
| `--days 90` | Lookback |
| `--max-fleets 6` | At/below active-enough line |
| `--affiliation Alliance` | `AffiliationType.name` |

## Executor: apply CSV

1. Review report (Previous → New, metrics, Story/Conf/Reason).
2. Delete CSV rows you want to keep active; save `on_leave_YYYY-MM-DD.csv` (UTF-8).
3. Admin: `/admin/groups/usercommunitystatus/bulk-upload/`
4. Upload file; optional default reason (prefer per-row reasons).
5. **Upload and apply** → Celery background; Discord role sync may take minutes.
6. Spot-check Community Status (`on_leave`) and Discord.

Bulk upload only (history + group sync). No prod shell writes.

## Related

- [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
- [academy-graduation](../academy-graduation/SKILL.md) (same behavior signals)
- `docs/auth/authorization.md`
