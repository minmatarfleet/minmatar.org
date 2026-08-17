---
name: trial-approval
description: >-
  Assess trial Alliance members for promotion to active (full members) using
  fleet attendance, solo/small-gang kills, and Discord voice, then produce a
  reviewer report and admin upload CSV. Use when approving trial, moving people
  off trial, graduating trial to active, reviewing who earned full membership,
  or running a trial hygiene pass.
---

# Trial Approval

Promote trial Alliance members to **`active`** when they are **participating in
the alliance** — not fleets alone. Solo / small-gang kills and Discord voice
count alongside fleet attendance. Deliver a **report + upload CSV**. Do not
change status yourself — the executor uploads after review.

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md).

## Policy

Trial is provisional. Full membership means they show up as part of the
alliance: alliance fleets, solo / small-gang combat, voice with the community,
or a clear mix.

We do **not** care just about fleets. We care about them doing things like solo
/ small gang kills, being in voice, etc. Participating in the alliance.

Participation must span the window — **do not approve on a strong first month
then silence**. Full-window totals alone are not enough; recent activity is
required.

`active` → affiliation group only (Trial Discord role stripped) via
`sync_user_community_groups`.

Bias: when unsure, **hold trial**. Resolve every case — no borderline dump.

Wrong-affiliation trials (Guest / Militia / `requires_trial=False`) are **not**
this pass — note them for `fix_trial_status_by_affiliation`.

This is not [on-leave](../on-leave/SKILL.md). Leave is fleet-primary (pings /
OPSEC). Trial approval is co-equal participation paths.

## Quick start

```bash
cd backend
pipenv run python ../.cursor/skills/trial-approval/scripts/fetch_trial_activity.py --json
```

Defaults: **90d** window + **30d** recent slice; affiliation **Alliance**;
status **trial**.

## Workflow

```
Task Progress:
- [ ] Fetch trial Alliance activity (--json)
- [ ] Split wrong-affiliation (fix command) vs real trial
- [ ] Apply recency gate (30d / days_since_activity)
- [ ] Decide approve / hold; Path + Conf + reason
- [ ] Emit report + CSV (approve rows only)
- [ ] Stop for executor review/upload
```

## Scope

| Filter | Value |
|--------|--------|
| Affiliation | `Alliance` (check prod name if fetch is empty) |
| Status | `trial` only |
| Activity | All linked `EveCharacter`s (account-level) |

## Signals

| Signal | Model | Roll-up |
|--------|--------|---------|
| Fleets | `EveFleetInstanceMember` | Distinct instances across linked EVE IDs |
| Kills | `EveCharacterKillmailAttacker` | Attackers; exclude self-victim; gang buckets |
| Voice | `DiscordChannelActivityRecord` | `voice_minute` by Django `username` → hours |

**Gang buckets** (attacker count on the killmail): small ≤10, medium 11–24,
large 25–39, blob 40+. Solo / small-gang = **small** bucket.

Fetch also emits a **30d recent slice** and ages:

| Field | Meaning |
|-------|---------|
| `fleets_30d` / `kills_30d` / `kills_small_30d` / `voice_hours_30d` | Same metrics, last 30d only |
| `days_since_fleet` / `days_since_kill` / `days_since_voice` | Age of latest event in window (`null` if none) |
| `days_since_activity` | Min of the three ages (`null` if fully dark in window) |

Login, mining, PI, industry alone do not clear the bar. Note ESI gaps / zero
linked chars / untracked ops in reasons when they matter.

## Decision rules (90d)

Paths are co-equal. Approve when **one strong path** or **two medium paths**,
**and** the recency gate passes **and** they have been in the alliance
**≥ 60 days** (60–90 days is a healthy trial; do not promote earlier).

**Strong path (approve, Conf high):**

1. Fleets ≥ 4
2. Small-gang kills ≥ 8 (small bucket)
3. Voice ≥ 10h **and** (fleets ≥ 1 or kills ≥ 3)

**Medium path — combine two for approve (Conf medium), or one strong + weak support:**

| Path | Medium bar |
|------|------------|
| Fleets | 2–3 |
| Small-gang | 4–7 |
| Total kills (any gang) | ≥ 10 with some small-gang (≥ 3) |
| Voice | ≥ 5h with any fleet or kill touch |

### Tenure gate (required for approve)

Participation is not enough if they just got here. Trial should run **60–90
days**. Approve only when current alliance tenure is **≥ 60 days**.

Tenure = current alliance stint across linked characters (corp history;
contiguous MFA corp transfers count as one stint). Fall back to accepted
application date, then community-status trial start, if history is missing.

**Too early — hold** even if path + recency would approve:

- `alliance_days` < 60 (including unknown tenure)
- Typical shape: strong first-month PAP, joined 1–4 weeks ago

Reason tag: `Too early — Nd in alliance; 60–90d is healthy. On track: …`
Conf: do not approve; re-eval at 60d. These are not CEO-nudge / fail cases.

Do **not** fail a trial before 60 days in alliance either — they have not had
a healthy window.

### Recency gate (required for approve)

Full-window strength is necessary but not sufficient.

**Recent enough to approve** when any of:

1. `days_since_activity` ≤ 30 (fleet, kill, or voice in the last 30d)
2. Or explicit 30d touch: `fleets_30d` ≥ 1 **or** `kills_30d` ≥ 1 **or** `voice_hours_30d` ≥ 1

**Front-loaded / stale — hold** even if 90d path clears:

- 90d totals would approve, but no recent touch (`days_since_activity` > 30 or
  null with only early-window activity) — they started strong then disappeared
- Typical shape: high `fleets` / `kills_small` over 90d, but `fleets_30d` = 0,
  `kills_30d` = 0, `voice_hours_30d` ≈ 0

Reason tag: `Front-loaded — … last activity Nd ago` (or `no activity in 30d`).
Conf: do not approve; hold for CEO contact / re-eval when they return.

Do **not** overweight month-one PAP: if almost all kills/fleets sit in the older
part of the window and the last 30d is quiet, hold.

**Hold trial:**

- Too early: path would clear, but < 60 days in alliance
- Dark: fleets ≤ 1, kills ≈ 0, voice ≈ 0
- Front-loaded / stale (above)
- Voice-only social ghost: high voice, no fleets, no kills
- Blob-only killboard with no fleets / no small-gang / no voice (unclear alliance play)
- No linked characters (caveat; Conf medium if somehow recommending — prefer hold)

Tag approve **Path**: `Fleet`, `Small-gang`, `Voice`, or `Mixed`.

Reason line: Path + 1–2 metrics; add last-activity age when non-obvious. See
[examples.md](examples.md).

## Deliverables

Always both. Sort approves by Conf (`high` then `medium`).

**Summary:** `N approve (H/M); E too-early holds; H held (F front-loaded); W wrong-affiliation. Window: 90d / recent 30d. Tenure ≥60d.`

### Report

| Username | Primary | Previous | New | Fleets | Kills | Small | Voice | 30d | Last | Path | Conf | Reason |
|----------|---------|----------|-----|-------:|------:|------:|------:|-----|------|------|------|--------|

- Previous = `trial`; New = `active`
- Voice as hours (`12.5h`)
- Small = small-gang kill count
- **30d** = short recent slice (`2F/5K/1.2h` or `quiet`)
- **Last** = `days_since_activity` (`12d` / `—`)
- Held / wrong-affiliation: counts only unless asked; call out front-loaded holds when relevant

### CSV (admin upload)

Approve rows only (recency gate already applied):

```csv
username,community_status,reason
someuser,active,Mixed — 5 fleets, 9 small-gang, 6h voice (90d; last 8d)
otheruser,active,Small-gang — 0 fleets, 14 small-gang kills (90d; last 3d)
```

`community_status` = `active`. `reason` ≤255. Username = Django username.

| Flag | Use |
|------|-----|
| `--days 90` | Lookback |
| `--affiliation Alliance` | `AffiliationType.name` |

## Executor: apply CSV

1. Review report (metrics, 30d/Last, Path/Conf/Reason). Treat front-loaded holds as Contact candidates, not silent Passes.
2. Delete rows you want to keep on trial; save `trial_approve_YYYY-MM-DD.csv` (UTF-8).
3. Admin: `/admin/groups/usercommunitystatus/bulk-upload/`
4. Upload; prefer per-row reasons.
5. **Upload and apply** → Celery; Discord role sync may take minutes.
6. Spot-check: status `active`, Trial role gone, Alliance role kept.

Bulk upload only. No prod shell writes. Small batches may use admin **Approve trial**.

Wrong-affiliation list → `pipenv run python manage.py fix_trial_status_by_affiliation` (with `--dry-run` first) on an environment that can write — not this skill’s CSV.

## Related

- [on-leave](../on-leave/SKILL.md) (fleet-primary; different question)
- [academy-graduation](../academy-graduation/SKILL.md) (same signals, corp routing)
- [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
- `docs/auth/authorization.md`
