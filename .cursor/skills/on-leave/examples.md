# On Leave — decision examples

90d soft line ≈ 3 fleets (~1/month). Report always pairs with CSV.

## Report + CSV pair

| Username | Primary | Previous | New | Fleets | Kills | Voice | Story | Conf | Reason |
|----------|---------|----------|-----|-------:|------:|------:|-------|------|--------|
| alice | Alice Alt | active | on_leave | 0 | 0 | 0h | Away | high | Away — no fleets, kills, or tracked voice in 90d. |

```csv
alice,on_leave,Away — 0 fleets, 0 kills, 0h voice (90d)
```

## Recommend

| Fleets | Kills | Voice | Story | Conf | Reason |
|-------:|------:|------:|-------|------|--------|
| 0 | 0 | 0h | Away | high | Away — no fleets, kills, or tracked voice in 90d. |
| 1 | 0 | 1h | Away | high | Away — one fleet touch, no combat, almost no voice. |
| 0 | 0 | 25h | OPSEC | high | OPSEC — Discord presence without tracked alliance fleets. |
| 0 | 3 | 15h | OPSEC | high | OPSEC — rare kills, no fleets; ping status not earned. |
| 0 | 40 | 10h | OPSEC | medium | OPSEC — strong killboard, zero tracked fleets (untracked ops possible). |
| 2 | 0 | 0h | Away | high | Away — under ~1/month with no supporting signal. |
| 3 | 0 | 0h | Away | medium | Away — on soft line, no kills/voice support. |

## Keep

| Fleets | Kills | Voice | Note |
|-------:|------:|------:|------|
| ≥6 | any | any | Active enough; low kills OK |
| 4 | 8 | 2h | Soft line + kills |
| 3 | 0 | 8h | Soft line + voice |
| 0 | 20 | 2h | Still **recommend** OPSEC medium — not keep |

## Exempt → omit

People Team, Technology Team, Tribe - Chief; Corp / Corporation Director (auth
group or `EveCorporation.directors`); named CEOs/LTI this session.

**Rejoin grace:** first 90d fleet within last 30d and no fleets in 30–180d prior
(e.g. `_obiwand` — one fleet after a long gap) → keep.
