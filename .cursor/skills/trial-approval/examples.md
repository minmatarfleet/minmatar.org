# Trial Approval — decision examples

90d window + 30d recent slice. Paths co-equal: fleets, solo/small-gang, voice.
Approve needs path strength **and** recent activity. Report always pairs with CSV.

## Report + CSV pair

| Username | Primary | Previous | New | Fleets | Kills | Small | Voice | 30d | Last | Path | Conf | Reason |
|----------|---------|----------|-----|-------:|------:|------:|------:|-----|------|------|------|--------|
| bob | Bob Main | trial | active | 5 | 12 | 9 | 6h | 2F/4K/2h | 8d | Mixed | high | Mixed — 5 fleets, 9 small-gang, 6h voice (90d; last 8d). |

```csv
bob,active,Mixed — 5 fleets, 9 small-gang, 6h voice (90d; last 8d)
```

## Approve

| Fleets | Small | Voice | 30d | Last | Path | Conf | Reason |
|-------:|------:|------:|-----|------|------|------|--------|
| 6 | 1 | 1h | 2F | 10d | Fleet | high | Fleet — 6 alliance fleets in 90d; last 10d. |
| 4 | 0 | 0h | 1F | 20d | Fleet | high | Fleet — 4 fleets; recent fleet touch. |
| 0 | 14 | 2h | 3K | 5d | Small-gang | high | Small-gang — 14 small-gang kills; active in 30d. |
| 1 | 8 | 0h | 2K | 12d | Small-gang | high | Small-gang — 8 small-gang kills with one fleet touch. |
| 2 | 3 | 12h | 1F/4h | 3d | Voice | high | Voice — 12h voice with fleet + kill touch. |
| 3 | 5 | 5h | 1F/2K | 15d | Mixed | medium | Mixed — medium fleets, small-gang, and voice. |

## Hold — front-loaded / stale

90d path would clear, but quiet in the last 30d → **hold**, do not approve.

| Fleets | Small | Voice | 30d | Last | Note |
|-------:|------:|------:|-----|------|------|
| 8 | 57 | 0.4h | quiet | 43d | Front-loaded — strong June PAP, gone since; hold. |
| 2 | 5 | 0h | quiet | 71d | Front-loaded — medium 90d path, cold >30d; hold. |
| 5 | 11 | 2.9h | quiet | 40d | Borderline stale — Contact / hold, not auto-Pass. |
| 4 | 0 | 0h | quiet | 72d | Fleet path on paper; last fleet >30d — hold. |

Reason examples:

- `Front-loaded — 8 fleets, 57 small-gang (90d) but quiet 30d; last activity 43d ago.`
- `Stale — clears 90d bar; no fleet/kill/voice in 30d.`

## Hold — other

| Fleets | Kills | Small | Voice | Note |
|-------:|------:|------:|------:|------|
| 0 | 0 | 0 | 0h | Dark — no alliance participation. |
| 1 | 0 | 0 | 0.5h | Near-dark — one fleet blip. |
| 0 | 0 | 0 | 20h | Voice-only social ghost — no combat or fleets. |
| 0 | 25 | 0 | 0h | Blob-only board, no small-gang / fleets / voice. |
| 2 | 2 | 1 | 1h | One medium path only — hold for more signal. |

## Wrong affiliation (omit from approve CSV)

Trial status but affiliation is Guest / Militia / `requires_trial=False` → list
for `fix_trial_status_by_affiliation`, do not put in this skill’s active CSV.
