# Trial Approval — decision examples

90d window. Paths co-equal: fleets, solo/small-gang, voice. Report always pairs
with CSV.

## Report + CSV pair

| Username | Primary | Previous | New | Fleets | Kills | Small | Voice | Path | Conf | Reason |
|----------|---------|----------|-----|-------:|------:|------:|------:|------|------|--------|
| bob | Bob Main | trial | active | 5 | 12 | 9 | 6h | Mixed | high | Mixed — 5 fleets, 9 small-gang, 6h voice (90d). |

```csv
bob,active,Mixed — 5 fleets, 9 small-gang, 6h voice (90d)
```

## Approve

| Fleets | Kills | Small | Voice | Path | Conf | Reason |
|-------:|------:|------:|------:|------|------|--------|
| 6 | 2 | 1 | 1h | Fleet | high | Fleet — 6 alliance fleets in 90d. |
| 4 | 0 | 0 | 0h | Fleet | high | Fleet — 4 fleets; clear ops participation. |
| 0 | 18 | 14 | 2h | Small-gang | high | Small-gang — 14 small-gang kills, almost no PAP. |
| 1 | 10 | 8 | 0h | Small-gang | high | Small-gang — 8 small-gang kills with one fleet touch. |
| 2 | 4 | 3 | 12h | Voice | high | Voice — 12h voice with fleet + kill touch. |
| 3 | 6 | 5 | 5h | Mixed | medium | Mixed — medium fleets, small-gang, and voice. |
| 2 | 12 | 4 | 6h | Mixed | medium | Mixed — 2 fleets, some small-gang, 6h voice. |

## Hold

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
