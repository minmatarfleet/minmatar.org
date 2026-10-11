# Fleet Behavior Intel — triage examples

Synthetic precedents. Prefer miss over false Escalate.

## Clear

| Pattern | Why Clear |
|---------|-----------|
| EU prime, 12 fleets all EU, doctrine 10/10, voice OK | Real TZ — not TzSkew |
| 1 EarlyExit on a cancelled formup (instance 8m) | One-off / short instance skipped |
| Newbro, 5 fleets, T1 frig on kitchen-sink (no doctrine) | Doctrine-null not counted |
| Named scout this session, frig every strat | Session exempt |

## Watch

| Metrics | Story | Note |
|---------|-------|------|
| 8 fleets, top FC 5/8, doctrine OK, voice OK | SelectiveAttend medium | Odd FC skew; re-check next month |
| 6 fleets, no-voice 5/6, doctrine OK | FleetNoVoice | Voice alone — coverage caveat |

## Talk

| Metrics | Story | Note |
|---------|-------|------|
| 9 fleets, early-exit 6/9 (4 still docked), doctrine 7/9 | EarlyExit | Habitual leave-before-undock; private talk |
| 7 fleets, low-effort 5/7 on doctrine fleets, voice mixed | LowEffortShip | Soft concern before Escalate |

## Escalate (candidate — needs second eyes)

| Metrics | Story | Note |
|---------|-------|------|
| 10 fleets, top FC 9/10, doctrine 1/8, early-exit 6/10 docked | SelectiveAttend+LowEffortShip+EarlyExit | Compound + evidence pack |
| 12 fleets, early-exit+docked 8/12, low-effort 7/10 doctrine | EarlyExit+LowEffortShip | Habitual ping-seat pattern |

## Evidence pack shape

```
### example_user (Example Pilot)
Story: EarlyExit+LowEffortShip | Conf: high | Outcome: (blank)
Metrics: fleets 10; early-exit 7/10 (5 docked); doctrine 2/8; top FC 4/10
Evidence:
- 2026-06-01 | fc_a | Alliance | Rifter | doctrine no | present ~8m / left early, docked | voice 0m
- 2026-06-08 | fc_b | Alliance | Capsule | doctrine no | present ~12m / left early, docked | voice 0m
Caveats: voice tracking incomplete; confirm not alt-swap mid-fleet
```
