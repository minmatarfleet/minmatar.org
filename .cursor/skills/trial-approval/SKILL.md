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

Defaults: **90d** window; affiliation **Alliance**; status **trial**.

## Workflow

```
Task Progress:
- [ ] Fetch trial Alliance activity (--json)
- [ ] Split wrong-affiliation (fix command) vs real trial
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

Login, mining, PI, industry alone do not clear the bar. Note ESI gaps / zero
linked chars / untracked ops in reasons when they matter.

## Decision rules (90d)

Paths are co-equal. Approve when **one strong path** or **two medium paths**.

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

**Hold trial:**

- Dark: fleets ≤ 1, kills ≈ 0, voice ≈ 0
- Voice-only social ghost: high voice, no fleets, no kills
- Blob-only killboard with no fleets / no small-gang / no voice (unclear alliance play)
- No linked characters (caveat; Conf medium if somehow recommending — prefer hold)

Tag approve **Path**: `Fleet`, `Small-gang`, `Voice`, or `Mixed`.

Reason line: Path + 1–2 metrics. See [examples.md](examples.md).

## Deliverables

Always both. Sort approves by Conf (`high` then `medium`).

**Summary:** `N approve (H/M); H held; W wrong-affiliation. Window: 90d.`

### Report

| Username | Primary | Previous | New | Fleets | Kills | Small | Voice | Path | Conf | Reason |
|----------|---------|----------|-----|-------:|------:|------:|------:|------|------|--------|

- Previous = `trial`; New = `active`
- Voice as hours (`12.5h`)
- Small = small-gang kill count
- Held / wrong-affiliation: counts only unless asked

### CSV (admin upload)

Approve rows only:

```csv
username,community_status,reason
someuser,active,Mixed — 5 fleets, 9 small-gang, 6h voice (90d)
otheruser,active,Small-gang — 0 fleets, 14 small-gang kills (90d)
```

`community_status` = `active`. `reason` ≤255. Username = Django username.

| Flag | Use |
|------|-----|
| `--days 90` | Lookback |
| `--affiliation Alliance` | `AffiliationType.name` |

## Executor: apply CSV

1. Review report (metrics, Path/Conf/Reason).
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
